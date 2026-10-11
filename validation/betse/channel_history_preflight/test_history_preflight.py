"""Bounded software checks, not native or coupled-trajectory acceptance."""

import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ctx = importlib.import_module("history_context")
independent = importlib.import_module("history_math")
checker = importlib.import_module("history_check")
workers = importlib.import_module("history_workers")
job = importlib.import_module("history_job")


@pytest.fixture(scope="module")
def plan():
    return ctx.c.read(ctx.PLAN)


@pytest.fixture(scope="module")
def data(plan):
    return ctx.data(plan)


def synthetic_native(data, plan):
    """Only a comparator fixture; actual native run belongs to the detached job."""
    ind = independent.ind
    rows = {}
    voltage = data["native_voltage_V"]
    for name, gates in plan["histories"].items():
        for step in plan["native_steps_s"]:
            kinetics = [ind.kinetics(v) for v in voltage]
            after = [ind.gate_values(v, gates, step) for v in voltage]
            target = [[float(k[0][j]) for k in kinetics] for j in range(2)]
            rows[name + f"/dt_{step:.8g}"] = {
                "voltage_V": voltage,
                "input_unchanged": True,
                "before": [[g] * len(voltage) for g in gates],
                "after": [[a[j] for a in after] for j in range(2)],
                "initial_open_derived": [gates[0] * gates[1]] * len(voltage),
                "open_after_native": [a[0] * a[1] for a in after],
                "equilibrium_gate": target,
                "target": target,
                "tau_s": [[float(k[1][j]) for k in kinetics] for j in range(2)],
                "dt_s": step,
            }
    return {
        "rows": rows,
        "native_gate_batch_updates": len(rows),
        "native_scalar_gate_updates": len(rows) * len(voltage),
    }


@pytest.fixture(scope="module")
def cells_numpy(data, plan):
    # Initial RHS only. No run/step/integration calls.
    return workers.cells(data, plan, backends=["numpy"])


@pytest.fixture(scope="module")
def comparison_fixture(data, plan, cells_numpy):
    selected = copy.deepcopy(plan)
    selected["backends"] = ["numpy"]
    return selected, synthetic_native(data, plan), cells_numpy


def test_registered_panel_and_prerequisite_anchor(plan):
    ctx.validate_plan(plan)
    assert plan["prerequisite_completion_sha256"] == ctx.PRIOR_SHA


@pytest.mark.parametrize(
    "field",
    [
        "production_changed",
        "coupled_trajectories_run",
        "reference_integration_run",
        "automatic_polling",
        "automatic_retry",
        "automatic_followup",
    ],
)
def test_expanded_scope_is_rejected(plan, field):
    changed = copy.deepcopy(plan)
    changed[field] = True
    with pytest.raises(ValueError):
        ctx.validate_plan(changed)


@pytest.mark.parametrize("variant", ["active_channel", "blocked_channel"])
def test_initial_gate_pair_is_the_only_data_change(data, plan, variant):
    a, b = (data["definitions"][variant + "/" + name] for name in ("a", "b"))
    assert independent.without_gates(a) == independent.without_gates(b)
    assert a != b
    before = copy.deepcopy(data)
    again = ctx.data(plan)
    again["definitions"][variant + "/a"]["model"]["cells"][0]["channel"]["initial_gate"]["m"] = 0
    assert data == before


@pytest.mark.parametrize("variant", ["active_channel", "blocked_channel"])
def test_hidden_history_has_same_visible_rates_and_distinct_opening_slope(data, plan, variant):
    p = data["parameters"][variant]
    a, b = (independent.initial_rates(p, plan["histories"][name]) for name in ("a", "b"))
    for field in a:
        if field != "gate_rate_per_s":
            assert a[field] == b[field]
    witness = independent.witness(p, plan["histories"]["a"], plan["histories"]["b"])
    assert min(witness["open_rate_difference_per_s"]) > 1.0
    curvature = witness["transfer_acceleration_difference_fmol_per_s2"]
    assert all(v < 0 if variant == "active_channel" else v == 0 for v in curvature)
    assert witness["integrated_prediction"] is False


@pytest.mark.parametrize("gates", [[0.2, 0.6], [0.1, 0.1], [0.0, 0.0]])
def test_duplicate_or_unequal_product_pair_is_rejected(data, gates):
    with pytest.raises(ValueError):
        independent.witness(data["parameters"]["active_channel"], [0.2, 0.6], gates)


@pytest.mark.parametrize("bad", [-0.01, 1.01, float("nan"), float("inf"), True])
def test_invalid_gate_data_is_rejected(data, bad):
    with pytest.raises(ValueError):
        independent.initial_rates(data["parameters"]["active_channel"], [bad, 0.6])


@pytest.mark.parametrize("count", [1, 2, 7])
def test_independent_arrays_use_data_axes_not_a_seven_cell_constant(data, count):
    d = copy.deepcopy(data["definitions"]["active_channel/a"])
    d["model"]["cells"] = d["model"]["cells"][:count]
    p = copy.deepcopy(data["parameters"]["active_channel"])
    for key, value in p.items():
        if isinstance(value, list):
            p[key] = value[:count]
    oracle = independent.initial_rates(p, [0.2, 0.6])
    state, rate = independent.expected_arrays(d, oracle)
    assert state["gate"][0][:count] == [0.2] * count
    assert state["gate"][0][count:] == [0.0] * (d["execution"]["channel_capacity"] - count)
    assert sum(rate["amount_increment"][1]) == pytest.approx(
        -rate["extracellular_amount_increment"][1][0]
    )


def test_complete_production_initial_numpy_state_rhs_and_candidates(data, comparison_fixture):
    plan, native, cells = comparison_fixture
    result = checker.check(data, plan, native, cells)
    assert result["failed_comparisons"] == 0, result["failures"][:3]
    assert result["candidate_definitions"] == 12
    assert result["cells_initial_rhs_evaluations"] == 4
    assert not result["history_trajectory_qualified"]


def test_eager_and_compiled_full_initial_rates_without_integration(data, plan, monkeypatch):
    import cells.core.runner as runner

    def forbidden(*args, **kwargs):
        raise AssertionError("Preparation must not integrate")

    monkeypatch.setattr(runner, "run", forbidden)
    monkeypatch.setattr(runner, "_run_segment", forbidden)
    result = workers.cells(data, plan)
    checked = checker.check(data, plan, synthetic_native(data, plan), result)
    assert checked["failed_comparisons"] == 0, checked["failures"][:3]
    assert checked["cells_initial_rhs_evaluations"] == 12
    assert result["cells_trajectory_runs"] == 0


@pytest.mark.parametrize("field", ["channel", "voltage", "count", "trajectory"])
def test_extra_array_axes_or_false_counts_are_rejected(data, comparison_fixture, field):
    plan, native, original = comparison_fixture
    cells = copy.deepcopy(original)
    row = cells["rows"]["active_channel/a/numpy"]
    array = ctx.prior.pilot.audit.preparation.array_record
    if field in {"channel", "voltage"}:
        record = row["channel"]["flux_fmol_per_s"] if field == "channel" else row["voltage"]
        expanded = array(np.asarray(record["values"] + [0.0]))
        if field == "channel":
            row["channel"]["flux_fmol_per_s"] = expanded
        else:
            row["voltage"] = expanded
    elif field == "count":
        cells["initial_rhs_evaluations"] += 1
    else:
        cells["cells_trajectory_runs"] = 1
    with pytest.raises(ValueError):
        checker.check(data, plan, native, cells)


@pytest.mark.parametrize(
    "fault",
    [
        "gate",
        "padding",
        "bath",
        "ledger",
        "definition",
        "layout",
        "voltage",
        "row",
        "grid",
        "bytes",
        "integration",
    ],
)
def test_comparator_rejects_mutated_saved_contracts(data, comparison_fixture, fault):
    plan, native, original = comparison_fixture
    data, cells = copy.deepcopy(data), copy.deepcopy(original)
    row = cells["rows"]["active_channel/b/numpy"]
    array = ctx.prior.pilot.audit.preparation.array_record
    if fault in {"gate", "padding", "bath", "ledger"}:
        field = {
            "gate": "gate",
            "padding": "amount_increment",
            "bath": "extracellular_amount_increment",
            "ledger": "channel_transferred",
        }[fault]
        a = np.asarray(row["rhs"][field]["values"])
        if fault == "padding":
            a[0, -1] = 1e-4
        else:
            a.flat[0] += 1e-4
        row["rhs"][field] = array(a)
    elif fault == "definition":
        data["definitions"]["active_channel/b"]["model"]["cells"][0]["cell"]["volume_pL"] *= 2
    elif fault == "layout":
        row["layout_sha256"]["owners"] = "0" * 64
    elif fault == "voltage":
        a = np.asarray(row["voltage"]["values"])
        a[0] = 0.001
        row["voltage"] = array(a)
    elif fault == "row":
        cells["rows"].pop("active_channel/a/numpy")
    elif fault == "grid":
        cells["candidates"]["active_channel/b"][0]["grid_s"][-1] = 0.003
    elif fault == "bytes":
        row["state"]["gate"]["bytes_sha256"] = "0" * 64
    else:
        row["integration_executed"] = True
    try:
        result = checker.check(data, plan, native, cells)
    except ValueError:
        return
    assert result["failed_comparisons"] > 0


@pytest.mark.parametrize("fault", ["fixture", "after", "open", "step", "shape", "row"])
def test_native_fixture_step_and_readout_corruption_is_rejected(data, comparison_fixture, fault):
    plan, original, cells = comparison_fixture
    native = copy.deepcopy(original)
    row = native["rows"]["a/dt_2.5e-05"]
    if fault == "fixture":
        row["before"][0][0] = 0.3
    elif fault == "after":
        row["after"][0][0] += 0.01
    elif fault == "open":
        row["open_after_native"][0] += 0.01
    elif fault == "step":
        row["dt_s"] *= 2
    elif fault == "shape":
        row["after"][0].append(0.2)
    else:
        native["rows"].pop("a/dt_2.5e-05")
    try:
        result = checker.check(data, plan, native, cells)
    except ValueError:
        return
    assert result["failed_comparisons"] > 0


def test_independent_imports_and_checker_need_no_model_process():
    source = (
        "import sys; sys.path.insert(0, " + repr(str(HERE)) + "); import history_context as c\n"
        "with c.prior.model_fence():\n"
        " import history_math, history_check\n"
        " p=c.c.read(c.PLAN); d=c.data(p)\n"
        " history_math.witness(d['parameters']['active_channel'], [0.2,0.6], [0.6,0.2])\n"
        "print('model_free_ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", source], capture_output=True, text=True, check=True, timeout=15
    )
    assert result.stdout.strip() == "model_free_ok"


def test_existing_output_is_rejected_before_registration(tmp_path):
    with pytest.raises(ValueError, match="fresh history"):
        job.register(tmp_path, tmp_path / "unused.xml")


def test_history_test_receipt_rejects_empty_or_failed_suite(tmp_path, monkeypatch):
    monkeypatch.setattr(ctx, "ROOT", tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir()
    report = reports / "invalid.xml"
    report.write_text('<testsuite tests="0" failures="0" errors="0" skipped="0"/>')
    with pytest.raises(ValueError):
        ctx.test_receipt(report)


def test_plan_is_json_roundtrip_stable(plan):
    assert json.loads(json.dumps(plan, allow_nan=False)) == plan
