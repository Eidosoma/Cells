"""Ordinary runner/lifecycle acceptance; extended matrix runs detached."""

import json
import subprocess
import sys
from dataclasses import replace

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec, parse_batch, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.runner import branch_checkpoint, run
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import kinetic_finite_extracellular as model
from cells.processes.electrochemistry import CHARGE_PER_FMOL
from tests.kinetic_finite_fixtures import ROOT, canonical, definition, evidence, spec_for

PLAN, REFERENCE = evidence()
CASES = PLAN["cases"]


def assert_history(a, b):
    for actual, expected in zip(a, b, strict=True):
        np.testing.assert_array_equal(actual, expected)


def test_compiled_smoke_and_off_grid_observations(tmp_path):
    spec = spec_for(CASES[0], end=0.0002, samples=[0.0, 0.000037, 0.0001, 0.0002])
    result = run(spec)
    assert result.final.time == 0.0002
    assert result.history.pump_cycles[-1, 0] > 0
    assert result.diagnostics["max_energy_balance_error_pJ"] < 2e-8
    np.testing.assert_allclose(
        result.observations.pump_work_J,
        -1e-15 * np.asarray(result.final.layout.pump_drive) * result.observations.pump_cycles,
        rtol=0,
        atol=0,
    )
    write_run(tmp_path / "run", result)
    summary = json.loads((tmp_path / "run/summary.json").read_text())
    assert summary["model"] == "finite_extracellular@2"
    assert summary["pump_law"] == "nak_atp_mass_action_positive@1"
    saved = load_snapshot(tmp_path / "run/checkpoint_final")
    assert saved.spec == spec
    assert_history(saved.checkpoint.state, result.final.state)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
@pytest.mark.parametrize("dt", [0.0001, 0.00005])
def test_saved_independent_trajectories_full_state_and_ledgers(case, dt, tmp_path):
    oracle = REFERENCE[case["id"]]
    spec = spec_for(case, dt=dt, samples=oracle["DOP853"]["times_s"])
    result = run(spec)
    # Preserve the trajectory before comparisons, including a rejected match.
    write_run(tmp_path / "run", result, checkpoint_times=(0.006,))
    n = len(case["volume_pL"])
    actual = canonical(vars(result.observations), n)
    comparisons = {}
    for method in ("DOP853", "Radau"):
        expected = np.asarray(oracle[method]["state"])
        ratio = np.abs(actual - expected) / (
            PLAN["state_atol"] + PLAN["state_rtol"] * np.abs(expected)
        )
        assert np.max(ratio) <= 1
        increment = expected[:, : 3 * n].reshape((-1, n, 3))
        capacitance = np.asarray(case["area_m2"]) * case["specific_capacitance_F_m2"]
        reference_voltage = np.asarray(
            case["initial_voltage_V"]
        ) + CHARGE_PER_FMOL / capacitance * np.sum(increment * case["valence"], axis=-1)
        voltage_error = np.max(np.abs(result.observations.voltage_V[:, :n] - reference_voltage))
        assert voltage_error <= PLAN["voltage_atol_V"]
        comparisons[method] = {
            "comparisons": actual.size,
            "max_error_over_budget": float(np.max(ratio)),
            "max_voltage_error_V": float(voltage_error),
        }
    assert result.diagnostics["max_global_balance_error_fmol"] < PLAN["material_atol_fmol"]
    assert result.diagnostics["max_countercharge_error_C"] < PLAN["charge_atol_C"]
    assert result.diagnostics["max_energy_balance_error_pJ"] < PLAN["energy_atol_pJ"]
    # Events preserve cumulative cycles, with right-continuous rate controls.
    if case["id"] == "pump_block_release":
        obs = result.observations
        blocked = (obs.times >= 0.004) & (obs.times < 0.006)
        assert np.all(obs.pump_cycles_per_s[blocked] == 0)
        assert np.all(obs.pump_cycles[blocked, 0] == obs.pump_cycles[blocked, 0][0])
    if case["id"] == "all_blocked":
        assert all(np.all(v == 0) for v in result.history)
    checkpoint = result.checkpoint_at(0.006)
    suffix = run(spec, checkpoint)
    assert_history(tuple(v[checkpoint.step_index :] for v in result.history), suffix.history)
    # Durable ordinary-runner artifacts in the detached job's explicit pytest
    # base directory, for later saved-data review rather than a JUnit-only claim.
    write_run(tmp_path / "resume", suffix)
    with (tmp_path / "comparison.json").open("x") as handle:
        json.dump(
            {
                "case": case["id"],
                "dt_s": dt,
                "methods": comparisons,
                "restart_bitwise_equal": True,
                "diagnostics": result.diagnostics,
            },
            handle,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )


def test_restart_branch_windows_eager_and_fresh_process(tmp_path):
    spec = spec_for(CASES[0], end=0.0004, samples=[0.0, 0.000073, 0.0002, 0.000317, 0.0004])
    result = run(spec)
    cp = result.checkpoint_at(0.0002)
    path = tmp_path / "checkpoint"
    write_snapshot(path, spec, cp)
    saved = load_snapshot(path)
    resumed = run(saved.spec, saved.checkpoint)
    assert_history(tuple(v[cp.step_index :] for v in result.history), resumed.history)
    command = [
        sys.executable,
        "-B",
        "-m",
        "cells",
        "resume",
        str(path),
        "--output",
        str(tmp_path / "fresh"),
    ]
    subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True, timeout=90)
    with np.load(tmp_path / "fresh/trajectory.npz", allow_pickle=False) as fresh:
        assert_history(tuple(fresh[name] for name in model.STATE_TYPE._fields), resumed.history)
    raw = spec.to_dict()
    raw["experiment"]["membrane_controls"][0]["pump"].append({"time": cp.time, "multiplier": 0.0})
    changed = parse_spec(raw)
    branch = run(changed, branch_checkpoint(spec, cp, changed))
    assert_history(tuple(v[0] for v in branch.history), cp.state)
    assert branch.history.pump_cycles[-1, 0] == cp.state.pump_cycles[0]
    assert branch.history.pump_cycles[-1, 0] < result.history.pump_cycles[-1, 0]
    eager = run(replace(spec, execution=replace(spec.execution, jit=False)))
    for a, b in zip(result.history, eager.history, strict=True):
        np.testing.assert_allclose(a, b, atol=1e-13, rtol=1e-12)
    windows = list(iter_windows(spec, WindowPolicy(2, "full")))
    merged = tuple(
        np.concatenate(
            [getattr(w.history, name)[0 if i == 0 else 1 :] for i, w in enumerate(windows)]
        )
        for name in model.STATE_TYPE._fields
    )
    assert_history(merged, result.history)


def test_heterogeneous_batches_and_independent_clock_cohorts():
    specs = [
        spec_for(case, end=end)
        for case, end in zip((CASES[0], CASES[-1]), (0.0002, 0.0003), strict=True)
    ]
    batch = BatchSpec(tuple(WorldSpec(i + 1, s) for i, s in enumerate(specs)), 2, 100, 2**28)
    result = run_batch(batch)
    for world in result.worlds.values():
        assert_history(world.history, run(world.spec).history)
    rounds = list(iter_batch_windows(batch, WindowPolicy(2, "full")))
    for identity, world in result.worlds.items():
        present = [r.worlds[identity] for r in rounds if identity in r.worlds]
        merged = tuple(
            np.concatenate(
                [getattr(w.history, name)[0 if i == 0 else 1 :] for i, w in enumerate(present)]
            )
            for name in model.STATE_TYPE._fields
        )
        assert_history(merged, world.history)
    raw = batch.to_dict()
    raw["worlds"][1]["simulation"]["model"]["cells"][0]["membrane"]["pump"] = None
    assert parse_batch(raw).worlds[1].simulation.model.membranes[0].pump is None


def combined_spec():
    raw = definition(CASES[-1], end=0.0002)
    raw["model"]["cells"][0]["channel"] = {
        "id": "channel_0",
        "membrane_id": "membrane_0",
        "species_id": "K",
        "kinetic_law": "betse_kv1p5_mh@1",
        "max_permeability_m_per_s": 1e-10,
        "abundance": 0.5,
        "initial_gate": {"m": 0.2, "h": 0.7},
    }
    raw["experiment"]["channel_controls"] = [
        {"channel_id": "channel_0", "schedule": [{"time": 0.0, "availability": 1.0}]}
    ]
    raw["model"]["junctions"] = [
        {
            "id": "edge_0",
            "from_cell": "cell_0",
            "to_cell": "cell_1",
            "area_m2": 1e-10,
            "permeability_m_per_s": {"Na": 1e-10, "K": 2e-10, "Cl": 1e-10},
            "residual_fraction": {"Na": 0.1, "K": 0.2, "Cl": 0.1},
            "gate": {
                "law": "symmetric_opposing_relaxation@1",
                "sensitivity_per_V": 100.0,
                "half_voltage_V": 0.05,
                "tau_s": 0.01,
                "initial_gate": 0.6,
            },
        }
    ]
    raw["experiment"]["junction_controls"] = [
        {"junction_id": "edge_0", "schedule": [{"time": 0.0, "open_fraction": 1.0}]}
    ]
    return parse_spec(raw)


def test_channels_junctions_compose_without_outside_edge_ownership():
    spec = combined_spec()
    y, layout = model.initial_values(spec)
    u = PhysicalIonicGraphControl(*(v[0] for v in control_values(spec, [0.0])))
    with_edge = model.rhs(y, u, layout, layout.active, xp=np)
    no_edge = model.rhs(
        y, u._replace(junction=np.zeros_like(u.junction)), layout, layout.active, xp=np
    )
    np.testing.assert_array_equal(
        with_edge.extracellular_amount_increment, no_edge.extracellular_amount_increment
    )
    assert np.any(with_edge.junction_transferred != 0) and np.any(
        with_edge.channel_transferred != 0
    )
    result = run(spec)
    assert result.diagnostics["max_energy_balance_error_pJ"] < 2e-8
    assert result.diagnostics["max_global_balance_error_fmol"] < 2e-11


def test_event_split_off_grid_and_no_observation_continuation():
    raw = definition(CASES[0], end=0.0002, samples=[0.0, 0.000061, 0.000071, 0.000072])
    raw["experiment"]["membrane_controls"][0]["pump"] += [
        {"time": 0.000071, "multiplier": 0.0},
        {"time": 0.000139, "multiplier": 1.0},
    ]
    spec = parse_spec(raw)
    result = run(spec)
    assert 0.000071 in result.times and 0.000139 in result.times
    obs = result.observations
    assert obs.pump_cycles_per_s[-2, 0] == obs.pump_cycles_per_s[-1, 0] == 0
    assert result.checkpoint_at(0.000071).event_index == 1
    end = run(spec, result.final)
    assert len(end.times) == 1 and len(end.observations.times) == 0
    with pytest.raises(ConfigError):
        result.checkpoint_at(0.000061)
