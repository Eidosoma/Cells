"""Design/input checks, not a suppression/release trajectory or native dispatch."""

import copy
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
design = importlib.import_module("release_design")
probes = importlib.import_module("release_probes")


@pytest.fixture(scope="module")
def plan():
    return design.c.read(design.PLAN)


def test_prerequisite_authentication_without_models_or_audit_replay():
    code = (
        f"import sys; sys.path.insert(0, {str(HERE)!r})\n"
        "import release_design as d\n"
        "with d.audit.model_fence():\n"
        " p=d.prerequisite()\n"
        " assert len(p['audit_files_sha256']) == 10\n"
        " assert len(p['capture_files_sha256']) == 291\n"
        "print('closed_source_identity_ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code], check=True, capture_output=True, text=True, timeout=15
    )
    assert result.stdout.strip() == "closed_source_identity_ok"


def test_registered_input_design_and_unchanged_instantaneous_budgets(plan):
    design.validate_plan(plan)
    old = design.c.read(probes.independent.ctx.PLAN)
    assert plan["relative_tolerance"] == old["relative"]
    assert all(old["absolute"][k] == v for k, v in plan["absolute_tolerances"].items())


@pytest.mark.parametrize(
    "key,value",
    [
        ("production_changed", True),
        ("native_dispatch_executed", True),
        ("new_trajectory_executed", True),
        ("reference_integration_executed", True),
        ("release_response_qualified", True),
        ("biology_validated", True),
        ("gpu_tested", True),
        ("automatic_followup", True),
        ("block_time_s", 0.0006),
        ("duration_s", 0.004),
        ("extra", False),
    ],
)
def test_changed_design_rejected(plan, key, value):
    changed = copy.deepcopy(plan)
    changed[key] = value
    with pytest.raises(ValueError):
        design.validate_plan(changed)


@pytest.mark.parametrize("time", [-1e-20, 0.002000001, float("inf"), float("nan"), True])
def test_bad_elapsed_control_time_rejected(plan, time):
    with pytest.raises(ValueError):
        design.availability(plan, "baseline", time)


@pytest.mark.parametrize("value", [-1e-20, 1.000001, float("inf"), float("nan"), True, "0"])
def test_invalid_availability_rejected(value):
    with pytest.raises(ValueError):
        design.native_diffusivity(5e-17, value)


@pytest.mark.parametrize("baseline", [-1e-20, float("inf"), float("nan"), True])
def test_invalid_native_baseline_rejected(baseline):
    with pytest.raises(ValueError):
        design.native_diffusivity(baseline, 1)


def test_native_parameter_is_absolute_input_not_cumulative_suppression():
    base = 5e-17
    assert [design.native_diffusivity(base, u) for u in (1, 0, 0.25, 1)] == [
        base,
        0,
        base / 4,
        base,
    ]
    assert design.native_diffusivity(0.0, 1.0) == 0.0


@pytest.mark.parametrize("condition", design.CONDITIONS)
@pytest.mark.parametrize("step", [25e-6, 12.5e-6, 6.25e-6])
def test_native_control_grid_aligns_switches_without_resampling(plan, condition, step):
    rows = design.native_intervals(plan, condition, step)
    assert len(rows) == round(plan["duration_s"] / step)
    assert rows[0]["start_s"] == 0 and rows[-1]["end_s"] == plan["duration_s"]
    assert all(a["end_s"] == b["start_s"] for a, b in zip(rows[:-1], rows[1:], strict=True))
    for row in rows:
        assert row["availability"] == design.availability(plan, condition, row["start_s"])
    if condition == "suppression_release":
        assert sum(row["availability"] == 0 for row in rows) == round(
            (plan["release_time_s"] - plan["block_time_s"]) / step
        )


def test_native_control_is_not_the_old_inclusive_endpoint_label(plan):
    rows = design.native_intervals(plan, "suppression_release", 25e-6)
    label = np.linspace(0.0, plan["duration_s"], len(rows))
    assert rows[20]["start_s"] == plan["block_time_s"]
    assert label[20] != rows[20]["start_s"]
    assert rows[-1]["start_s"] < label[-1] == plan["duration_s"]


@pytest.mark.parametrize("history", ["a", "b"])
@pytest.mark.parametrize("condition", design.CONDITIONS)
def test_only_controls_change_not_hidden_state_or_intrinsic_physics(plan, history, condition):
    d = design.definition(plan, history, condition, 50e-6)
    base = design.view(history)["cells_definitions"]["active_channel/jax_jit/dt_5e-05"]
    assert d["model"] == base["model"] and d["execution"] == base["execution"]
    assert {k: v for k, v in d["experiment"].items() if k != "channel_controls"} == {
        k: v for k, v in base["experiment"].items() if k != "channel_controls"
    }
    assert [c["channel_id"] for c in d["experiment"]["channel_controls"]] == [
        c["channel_id"] for c in base["experiment"]["channel_controls"]
    ]
    assert all(
        c["schedule"] == design.schedule(plan, condition)
        for c in d["experiment"]["channel_controls"]
    )
    d["experiment"]["channel_controls"][0]["schedule"][0]["availability"] = 0.7
    assert base == design.view(history)["cells_definitions"]["active_channel/jax_jit/dt_5e-05"]


@pytest.mark.parametrize("history", ["a", "b"])
@pytest.mark.parametrize("condition", design.CONDITIONS)
@pytest.mark.parametrize("step", [50e-6, 25e-6, 12.5e-6])
def test_real_cells_timeline_and_right_continuous_controls(plan, history, condition, step):
    from cells.core.resources import trace_bytes
    from cells.core.runner import timeline
    from cells.core.schedule import control_values, event_index
    from cells.core.specs import parse_spec

    spec = parse_spec(design.definition(plan, history, condition, step))
    grid = timeline(spec)  # Preflight only; no rollout or integration step.
    assert plan["block_time_s"] in grid and plan["release_time_s"] in grid
    assert len(grid) - 1 == round(plan["duration_s"] / step)
    assert trace_bytes(spec, len(grid) - 1) <= spec.execution.max_trace_bytes
    queries = [0.0, plan["duration_s"]]
    for t in (plan["block_time_s"], plan["release_time_s"]):
        queries += [math.nextafter(t, -math.inf), t, math.nextafter(t, math.inf)]
    u = control_values(spec, queries)
    n = len(spec.model.channels)
    for i, time in enumerate(queries):
        assert np.array_equal(
            u.channel[i, :n], np.full(n, design.availability(plan, condition, time))
        )
        assert np.count_nonzero(u.channel[i, n:]) == 0
        assert np.count_nonzero(u.membrane[i]) == np.count_nonzero(u.junction[i]) == 0
    interval = control_values(spec, grid[:-1]).channel
    for t in (plan["block_time_s"], plan["release_time_s"]):
        index = grid.tolist().index(t)
        assert interval[index - 1, 0] == design.availability(
            plan, condition, math.nextafter(t, 0.0)
        )
        assert interval[index, 0] == design.availability(plan, condition, t)
        assert event_index(spec, t) == sum(c.time <= t for c in spec.experiment.changes) - 1
    changed_observers = spec.to_dict()
    changed_observers["experiment"]["observation_times"] = [0.0, 0.000537, 0.001137, 0.002]
    assert np.array_equal(timeline(parse_spec(changed_observers)), grid)


def test_pinned_native_transport_and_gate_source_boundary():
    result = design.pinned_source_contract()
    assert not result["native_dispatch_executed"]
    assert not result["alpha_expression_changed"]


@pytest.mark.parametrize("fault", ["omitted_maximum", "wrong_order", "modulated_kinetics"])
def test_changed_native_source_contract_rejected(fault):
    folder = design.c.SOURCE / "betse/science"
    network = (folder / "chemistry/networks.py").read_text()
    gates = (folder / "channels/vg_k.py").read_text()
    if fault == "omitted_maximum":
        network = network.replace("chan.maxDm*moddy", "moddy")
    elif fault == "wrong_order":
        network = network.replace("chan.channel_core.run(sim.vm, p)", "pass")
    else:
        gates = gates.replace(
            "self._calculate_state(V)", "self._calculate_state(V * self.modulator)"
        )
    with pytest.raises((ValueError, KeyError)):
        design.source_contract(network, gates)


@pytest.fixture(scope="module")
def evaluated(plan):
    import cells.core.runner as runner
    import cells.numerics.fixed_step as steps

    def forbidden(*args, **kwargs):
        raise AssertionError("Input design must not integrate")

    with pytest.MonkeyPatch.context() as patch:
        for module, name in (
            (runner, "run"),
            (runner, "_run_segment"),
            (runner, "_rollout"),
            (steps, "rk4_step"),
            (steps, "rk4_checked_step"),
        ):
            patch.setattr(module, name, forbidden)
        result = probes.cells_probes(plan)
    return result


def test_all_real_backend_full_rhs_probes_pass_independent_arithmetic(plan, evaluated):
    result = probes.check(plan, evaluated)
    assert result["rhs_evaluations"] == 54
    assert result["failed_comparisons"] == 0, result["failures"][:4]
    assert not result["new_trajectory_executed"] and not result["release_response_qualified"]


@pytest.mark.parametrize("history", ["a", "b"])
@pytest.mark.parametrize("time", [0.0, 0.0005, 0.001])
@pytest.mark.parametrize("backend", ["numpy", "jax_eager", "jax_jit"])
def test_block_preserves_hidden_rates_full_state_and_accumulated_ledgers(
    evaluated, history, time, backend
):
    rows = [evaluated["rows"][f"{history}/{time:.8g}/{u:g}/{backend}"] for u in (0, 0.25, 1)]
    assert rows[0]["state"] == rows[1]["state"] == rows[2]["state"]
    assert rows[0]["rhs"]["gate"] == rows[1]["rhs"]["gate"] == rows[2]["rhs"]["gate"]
    assert np.count_nonzero(rows[0]["rhs"]["gate"]) > 0
    for name, value in rows[0]["rhs"].items():
        if name != "gate":
            assert np.count_nonzero(value) == 0
    assert np.count_nonzero(rows[0]["flux_fmol_per_s"]) == 0
    assert np.count_nonzero(rows[2]["flux_fmol_per_s"]) > 0
    np.testing.assert_allclose(
        rows[1]["flux_fmol_per_s"], np.asarray(rows[2]["flux_fmol_per_s"]) / 4, rtol=2e-14, atol=0
    )
    if time > 0:
        assert np.count_nonzero(rows[0]["state"]["channel_transferred"]) > 0
        assert np.count_nonzero(rows[0]["state"]["extracellular_amount_increment"]) > 0


@pytest.mark.parametrize(
    "fault", ["state", "gate", "transfer", "outside", "row", "metadata", "padding", "scope"]
)
def test_corrupted_production_probes_rejected(plan, evaluated, fault):
    changed = copy.deepcopy(evaluated)
    key = "a/0.0005/0/numpy"
    row = changed["rows"][key]
    if fault == "state":
        row["state"]["channel_transferred"][0] = 0.0
    elif fault == "gate":
        row["rhs"]["gate"][0][0] += 1
    elif fault == "transfer":
        row["rhs"]["channel_transferred"][0] = 1e-30
    elif fault == "outside":
        row["rhs"]["extracellular_amount_increment"][1][0] = 1e-30
    elif fault == "row":
        changed["rows"]["unexpected"] = row
    elif fault == "metadata":
        row["availability"] = 1.0
    elif fault == "padding":
        row["rhs"]["gate"][0].append(0.0)
    else:
        changed["new_trajectory_executed"] = True
    try:
        result = probes.check(plan, changed)
    except (ValueError, KeyError):
        return
    assert result["failed_comparisons"] > 0


def test_independent_control_and_math_modules_do_not_import_models():
    code = (
        f"import sys; sys.path.insert(0, {str(HERE)!r})\n"
        "import release_design as d\n"
        "with d.audit.model_fence():\n"
        " import release_probes\n"
        " d.pinned_source_contract()\n"
        " assert len(d.native_intervals(d.c.read(d.PLAN), 'suppression_release', 25e-6)) == 80\n"
        "print('model_free_design_ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code], check=True, capture_output=True, text=True, timeout=15
    )
    assert result.stdout.strip() == "model_free_design_ok"


def test_plan_serializes_without_nonfinite_or_boolean_numeric_substitutions(plan):
    changed = copy.deepcopy(plan)
    changed["duration_s"] = True
    assert json.dumps(plan, sort_keys=True) != json.dumps(changed, sort_keys=True)
    with pytest.raises(ValueError):
        design.validate_plan(changed)
