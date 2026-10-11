"""Prospective control semantics, reference discontinuities and resource guards."""

import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiment as x  # noqa: E402
import reference as reference  # noqa: E402


def setup():
    protocol = x.u.read(Path(__file__).with_name("protocol.json"))
    preparation = x.u.read(
        Path("/mnt/workspaces/Cells/ref-005e-fresh-20260919-01/prepare/preparation.json")
    )
    return protocol, preparation


def tiny():
    protocol, preparation = setup()
    protocol.update(
        duration_s=0.001,
        block_time_s=0.00025,
        release_time_s=0.0005,
        sample_dt_s=0.00005,
        reference_step_divisors=[20, 40, 40],
    )
    return protocol, preparation


def test_retains_physics_and_scientific_tolerances():
    protocol, preparation = setup()
    original = copy.deepcopy(preparation)
    plan = x.plan(protocol)
    for name in ("mapping", "trajectory", "accounting", "refinement"):
        assert plan[name] == x.u.plan()[name]
    for arm in protocol["arms"]:
        case = x.case(preparation, arm, protocol)
        assert {k: v for k, v in case.items() if k not in ("id", "end_time_s", "controls")} == {
            k: v
            for k, v in preparation["cases"]["pump_leak"].items()
            if k not in ("id", "end_time_s", "controls")
        }
    assert preparation == original


@pytest.mark.parametrize(
    "arm,blocked,released",
    [
        ("baseline", 1, 1),
        ("no_op", 1, 1),
        ("held_block", 0, 0),
        ("block_release", 0, 1),
        ("half_release", 0.5, 1),
    ],
)
def test_controls_are_right_continuous_and_do_not_change_leaks(arm, blocked, released):
    protocol, preparation = setup()
    case = x.case(preparation, arm, protocol)
    rows = case["controls"]
    assert x.control_at(rows, np.nextafter(protocol["block_time_s"], 0)) == (1, 1)
    assert x.control_at(rows, protocol["block_time_s"]) == (blocked, 1)
    assert x.control_at(rows, protocol["release_time_s"]) == (released, 1)
    raw = x.definition(preparation, arm, protocol, protocol["cells_steps_s"][0], "gpu")
    assert raw["execution"]["backend"] == "gpu"
    for membrane in raw["experiment"]["membrane_controls"]:
        assert membrane["pump"] == [
            dict(time=t, multiplier=v) for t, v in x.controls(arm, protocol)
        ]
        assert membrane["leak"] == [
            dict(time=0.0, multipliers=dict.fromkeys(["Na", "K", "Cl"], 1.0))
        ]


def test_all_full_grids_have_exact_event_checkpoints_and_fit_memory():
    protocol, preparation = setup()
    rows = x.preflight(preparation, protocol)["rows"]
    assert len(rows) == 15 and max(r["steps"] for r in rows) == 8000
    protocol["resources"]["max_trace_bytes"] = 1
    with pytest.raises(ValueError):
        x.preflight(preparation, protocol)


@pytest.mark.parametrize("arm", ["block_release", "held_block", "half_release"])
def test_independent_reference_preserves_state_and_histories_at_switches(arm):
    protocol, preparation = tiny()
    plan = x.plan(protocol)
    case = x.case(preparation, arm, protocol)
    record = reference.integrate(case, plan["reference"]["solves"][0], plan)
    assert len(record["times_s"]) == len(record["states"]) == 21
    assert len(record["segments"]) == 3
    for left, right in zip(record["segments"], record["segments"][1:], strict=False):
        assert left["final"] == right["initial"]
    block = record["segments"][1]
    if arm != "half_release":
        assert block["initial"][45:52] == block["final"][45:52]
    assert any(v != 0 for v in block["initial"])
    assert record["steady_state_qualified"] is False
    assert (
        record["accounting_maxima"]["energy_residual_pJ"] <= plan["accounting"]["cells_energy_pJ"]
    )


def test_reference_work_cap_is_enforced_before_a_result():
    protocol, preparation = tiny()
    protocol["reference_rhs_cap"] = 1
    plan = x.plan(protocol)
    with pytest.raises(ValueError, match="RHS cap"):
        reference.integrate(
            x.case(preparation, "block_release", protocol), plan["reference"]["solves"][0], plan
        )
