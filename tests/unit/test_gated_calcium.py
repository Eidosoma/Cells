"""Cav1.2 kinetics, finite calcium transport and complete CPU/L4 replay."""

import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine as assembly
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import parse_batch, run_batch
from cells.core.batch_windows import run_batch_windowed
from cells.core.devices import execution_device
from cells.core.errors import NumericalError
from cells.core.gated_calcium_spec import base_spec
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, run_windowed
from cells.ensemble.plan import jupiter_plan, plan
from cells.io import load_snapshot, write_run
from cells.models import gated_calcium as model
from cells.processes import calcium_gates as process
from tests.batch_fixtures import definition
from tests.reference_gated_calcium import (
    F,
    R,
    System,
    native_channel,
    physical_energy_derivative,
    reference,
    scalar_flux,
    scalar_kinetics,
)
from tests.unit.test_assembly_cluster import ensemble_definition, event_histories
from tests.unit.test_spatial_calcium import compare, same

ROOT = Path(__file__).resolve().parents[2]
BACKEND = os.environ.get("CELLS_CAV_TEST_BACKEND", "cpu")


def data():
    raw = json.loads((ROOT / "configs/gated_calcium_cluster.json").read_text())
    raw["execution"]["backend"] = BACKEND
    return raw


def assembly_data():
    return json.loads((ROOT / "configs/assembly_regulated_gated_calcium_cluster.json").read_text())


def evidence(name, record=None, arrays=None):
    target = os.environ.get("CELLS_CAV_EVIDENCE")
    if target:
        path = Path(target) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        if record is not None:
            (path / (name + ".json")).write_text(
                json.dumps(record, indent=2, allow_nan=False) + "\n"
            )
        if arrays is not None:
            np.savez_compressed(path / (name + ".npz"), **arrays)


def test_native_cav1p2_units_shift_powers_and_held_voltage():
    voltage = np.array([-0.12, -0.08, -0.06, -0.02, 0.0, 0.06])
    native, update = native_channel()
    native._init_state(1000 * voltage)
    native._calculate_state(1000 * voltage)
    expected = np.stack((native._mInf, native._hInf))
    tau = np.stack((native._mTau, native._hTau)) / native.time_unit
    actual, periods = process.kinetics(voltage, xp=np)
    np.testing.assert_allclose(actual, expected, rtol=3e-14, atol=3e-16)
    np.testing.assert_allclose(periods, tau, rtol=3e-14, atol=3e-16)
    np.testing.assert_allclose(np.stack((native.m, native.h)), actual, rtol=3e-14, atol=3e-16)
    assert (native._mpower, native._hpower) == (2, 1)
    gate = np.full((2, len(voltage)), 0.4)
    np.testing.assert_array_equal(
        process.open_probability(gate), gate[0] ** native._mpower * gate[1] ** native._hpower
    )
    # Native is semi-implicit; its refinement must approach the continuous law.
    errors = []
    for dt in (0.001, 0.0005, 0.00025):
        native.m, native.h = gate.copy()
        for _ in range(round(0.004 / dt)):
            update(native, SimpleNamespace(dt=dt), time_unit=native.time_unit)
        exact = expected + (gate - expected) * np.exp(-0.004 / tau)
        errors.append(float(np.max(np.abs(np.stack((native.m, native.h)) - exact))))
    assert errors[0] / errors[1] > 1.8 and errors[1] / errors[2] > 1.8
    with jax.default_device(execution_device(BACKEND)):
        compiled = jax.jit(process.kinetics)(voltage)
        assert compiled[0].device.platform == BACKEND
        for value, want in zip(compiled, (expected, tau), strict=True):
            np.testing.assert_allclose(value, want, rtol=3e-14, atol=3e-16)
        derivative = jax.jacfwd(process.kinetics)(np.array([0.0]))[0]
        finite = (scalar_kinetics(1e-7)[0] - scalar_kinetics(-1e-7)[0]) / 2e-7
        np.testing.assert_allclose(np.asarray(derivative)[:, 0, 0], finite, rtol=2e-9, atol=1e-9)
    evidence(
        "native-laws",
        {
            "status": "passed",
            "points": len(voltage),
            "voltage_shift_V": -0.010,
            "powers": [2, 1],
            "native_discrete_refinement_errors": errors,
            "scope": (
                "Pinned targets/time constants and powers; "
                "continuous Cells ODE differs from native discrete updater"
            ),
        },
    )


@pytest.mark.parametrize(
    "case",
    [
        "missing_channel",
        "duplicate_owner",
        "duplicate_id",
        "unknown_owner",
        "id_collision",
        "species",
        "law",
        "negative_permeability",
        "negative_abundance",
        "bad_gate",
        "nan_gate",
        "bool_gate",
        "missing_control",
        "duplicate_control",
        "unknown_control",
        "late_start",
        "repeat_time",
        "availability",
        "loss_bound",
        "old_identity",
    ],
)
def test_invalid_channel_definitions(case):
    raw = data()
    channels, controls = (
        raw["model"]["calcium_channels"],
        raw["experiment"]["calcium_channel_controls"],
    )
    if case == "missing_channel":
        channels.pop()
    elif case == "duplicate_owner":
        channels[1]["membrane_id"] = channels[0]["membrane_id"]
    elif case == "duplicate_id":
        channels[1]["id"] = channels[0]["id"]
    elif case == "unknown_owner":
        channels[0]["membrane_id"] = "absent"
    elif case == "id_collision":
        channels[0]["id"] = "channel_0"
    elif case == "species":
        channels[0]["species_id"] = "K"
    elif case == "law":
        channels[0]["kinetic_law"] = "betse_kv1p5_mh@1"
    elif case == "negative_permeability":
        channels[0]["max_permeability_m_per_s"] = -1
    elif case == "negative_abundance":
        channels[0]["abundance"] = -1
    elif case in ("bad_gate", "nan_gate", "bool_gate"):
        channels[0]["initial_gate"]["m"] = {
            "bad_gate": 1.1,
            "nan_gate": float("nan"),
            "bool_gate": True,
        }[case]
    elif case == "missing_control":
        controls.pop()
    elif case == "duplicate_control":
        controls[1] = copy.deepcopy(controls[0])
    elif case == "unknown_control":
        controls[0]["channel_id"] = "absent"
    elif case == "late_start":
        controls[0]["schedule"][0]["time"] = 0.001
    elif case == "repeat_time":
        controls[0]["schedule"] *= 2
    elif case == "availability":
        controls[0]["schedule"][0]["availability"] = 1.01
    elif case == "loss_bound":
        channels[0].update(max_permeability_m_per_s=1e-3, abundance=1e6)
    elif case == "old_identity":
        raw["model"]["id"] = "spatial_calcium@2"
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


def test_stage_ownership_charge_energy_and_calcium_reversal():
    spec = parse_spec(data())
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0])
    c = type(controls)(*(v[0] for v in controls))
    actual = model.rhs(state, c, p, p.active, xp=np)
    disabled = model.rhs(state, c._replace(calcium_channel=0.0), p, p.active, xp=np)
    raw = spec.to_dict()
    system = System(raw)
    y = system.initial()
    dy = system.rhs(y, 0.0)
    expected = system.unpack(dy)
    for key, value in system.flatten_actual(actual._asdict()).items():
        np.testing.assert_allclose(value, expected[key], rtol=3e-11, atol=3e-13, err_msg=key)
    delta = actual.amount_increment - disabled.amount_increment
    np.testing.assert_allclose(
        delta[p.plasma_ca, :2], actual.calcium_channel_transferred[:2], rtol=0, atol=3e-17
    )
    np.testing.assert_allclose(
        np.sum(p.valence * delta, axis=0)[:2],
        2 * actual.calcium_channel_transferred[:2],
        rtol=0,
        atol=3e-17,
    )
    np.testing.assert_allclose(
        delta.sum(axis=1)
        + (actual.extracellular_amount_increment - disabled.extracellular_amount_increment).sum(
            axis=1
        ),
        0,
        rtol=0,
        atol=3e-14,
    )
    for i in range(2):
        local = model.store_layout(p, i)
        assert np.all(
            (actual.chemical_amount_increment - disabled.chemical_amount_increment)[i, :, local.er]
            == 0
        )
    diss = sum(np.sum(getattr(actual, k)) for k in actual._fields if "dissipated_energy" in k)
    work = -1e-3 * np.sum(p.pump_drive * actual.pump_cycles)
    for i in range(2):
        local = model.store_layout(p, i)
        work -= (
            1e-3
            * model.er.processes.chemical_drive(
                model.er.pump_parameters(local), local.temperature, xp=np
            )
            * actual.er_pump_transferred[i, 0]
        )
    work -= 1e-3 * np.sum(model.base.readouts(state, p, xp=np)[-1] * actual.plasma_pump_cycles)
    residual = physical_energy_derivative(system, y, dy) + diss - work
    assert abs(residual) < 2e-12
    from cells.processes.electrochemistry import ghk_leak

    ci, co, t = 0.002, 0.008, 298.15
    reversal = R * t / (2 * F) * np.log(co / ci)
    v = reversal + np.array([-0.02, 0, 0.02])
    got = np.asarray(ghk_leak(ci, co, v, 2, t, 3e-10, 2e-6, 1.0, xp=np))
    want = np.array([scalar_flux(ci, co, x, t, 3e-10, 2e-6)[0] for x in v])
    np.testing.assert_allclose(got, want, rtol=3e-12, atol=3e-16)
    assert got[0] > 0 > got[2] and abs(got[1]) < 3e-16
    evidence(
        "ownership",
        {
            "status": "passed",
            "energy_derivative_residual_pJ_per_s": float(residual),
            "calcium_reversal_voltage_V": float(reversal),
        },
    )


@pytest.mark.parametrize("variant", ["blocked", "zero_permeability", "zero_abundance", "switch"])
def test_channel_interventions_and_previous_model_reduction(variant):
    raw = data()
    raw["experiment"].update(end_time=0.001, observation_times=[0, 0.00037, 0.001])
    for ch, ctrl in zip(
        raw["model"]["calcium_channels"], raw["experiment"]["calcium_channel_controls"], strict=True
    ):
        if variant == "blocked":
            ctrl["schedule"][0]["availability"] = 0
        elif variant == "zero_permeability":
            ch["max_permeability_m_per_s"] = 0
        elif variant == "zero_abundance":
            ch["abundance"] = 0
    if variant == "switch":
        raw["experiment"]["calcium_channel_controls"][0]["schedule"].append(
            {"time": 0.000413, "availability": 0}
        )
        raw["experiment"]["plasma_controls"][1]["schedule"].append(
            {"time": 0.000713, "pump": 0.4, "exchanger": 0.2}
        )
        er = raw["experiment"]["store_controls"][0]["controls"]
        er.append(copy.deepcopy(er[0]) | {"time": 0.000613, "release": 0})
    result = run(parse_spec(raw))
    if variant != "switch":
        old = run(base_spec(result.spec))
        for field in old.history._fields:
            np.testing.assert_array_equal(
                getattr(result.history, field), getattr(old.history, field), err_msg=field
            )
        assert np.all(result.history.calcium_channel_transferred == 0)
        assert np.all(result.history.calcium_channel_dissipated_energy_pJ == 0)
        assert not np.array_equal(result.history.calcium_gate[0], result.history.calcium_gate[-1])
    else:
        canonical = result.spec.to_dict()
        compare(
            vars(result.observations),
            reference(canonical, result.observations.times),
            System(canonical),
        )
    evidence("control-" + variant, {"status": "passed", "diagnostics": result.diagnostics})


@pytest.mark.parametrize(
    "case", ["transfer", "energy", "negative_energy", "gate", "nan_gate", "padding"]
)
def test_corrupt_checkpoint_rejected(baseline, case):
    state = model.State(*(np.array(v) for v in baseline.final.state))
    if case == "transfer":
        state.calcium_channel_transferred[0] += 1e-5
    elif case == "energy":
        state.calcium_channel_dissipated_energy_pJ[0] += 1e-5
    elif case == "negative_energy":
        state.calcium_channel_dissipated_energy_pJ[0] = -1e-5
    elif case == "gate":
        state.calcium_gate[0, 0] = 1.1
    elif case == "nan_gate":
        state.calcium_gate[0, 0] = np.nan
    elif case == "padding":
        state.calcium_gate[0, -1] = 0.5
    with pytest.raises(NumericalError):
        validate_checkpoint(baseline.spec, replace(baseline.final, state=state))


@pytest.mark.parametrize("field", ["calcium_gate", "calcium_channel_dissipated_energy_pJ"])
def test_cubic_enclosure_rejects_interior_excursions(field):
    state, p = model.initial_values(parse_spec(data()))
    history = model.State(*(np.stack((v, v)) for v in state))
    left = model.State(*(np.zeros_like(v[:1]) for v in history))
    right = model.State(*(np.zeros_like(v[:1]) for v in history))
    getattr(left, field).flat[0] = 1e5
    getattr(right, field).flat[0] = -1e5
    with pytest.raises(NumericalError, match="Calcium channel cubic"):
        model.check_interpolants(np.array([0, 0.001]), history, left, right, p)


@pytest.fixture(scope="module")
def baseline():
    result = run(parse_spec(data()))
    assert all(v.device.platform == BACKEND for v in result.final.state)
    evidence(
        "baseline",
        {"status": "passed", "diagnostics": result.diagnostics},
        result.history._asdict(),
    )
    return result


def test_canonical_schema_and_complete_artifacts(baseline, tmp_path):
    raw = data()
    raw["model"]["calcium_channels"].reverse()
    raw["experiment"]["calcium_channel_controls"].reverse()
    assert parse_spec(raw) == baseline.spec == parse_spec(baseline.spec.to_dict())
    for key in model.EXTRA_FIELDS:
        assert np.all(getattr(baseline.history, key)[..., 2:] == 0)
    assert np.any(baseline.history.calcium_channel_transferred[-1] > 0)
    assert np.all(baseline.history.calcium_channel_dissipated_energy_pJ >= 0)
    summary = write_run(tmp_path / "public", baseline)
    assert summary["model"] == "spatial_calcium@3"
    saved = load_snapshot(tmp_path / "public/checkpoint_final")
    same(saved.checkpoint.state, baseline.final.state)
    same(saved.checkpoint.layout, baseline.final.layout)


def test_independent_references_and_timestep_refinement(baseline):
    raw = baseline.spec.to_dict()
    system = System(raw)
    refs = [reference(raw, baseline.observations.times, method=m) for m in ("DOP853", "Radau")]
    errors = {}
    for method, expected in zip(("DOP853", "Radau"), refs, strict=True):
        errors[method] = compare(vars(baseline.observations), expected, system)
        evidence(
            "reference-" + method,
            {"rhs_calls": expected["rhs_calls"]},
            {k: v for k, v in expected.items() if k != "rhs_calls"},
        )
    for key in system.shapes:
        np.testing.assert_allclose(refs[0][key], refs[1][key], rtol=2e-10, atol=5e-14, err_msg=key)
    convergence = []
    for dt in (0.000025, 0.0000125, 0.00000625):
        raw["execution"]["dt"] = dt
        result = baseline if dt == 0.0000125 else run(parse_spec(raw))
        actual = system.flatten_actual(vars(result.observations))["chemical_amount_increment"]
        convergence.append(float(np.max(np.abs(actual - refs[0]["chemical_amount_increment"]))))
    assert convergence[0] / convergence[1] > 6 and convergence[1] / convergence[2] > 6
    evidence(
        "independent-reference",
        {
            "status": "passed",
            "max_errors": errors,
            "steps_s": [0.000025, 0.0000125, 0.00000625],
            "refinement_errors_fmol": convergence,
        },
    )


def test_complete_restart_windows_partitions_and_future_controls(tmp_path):
    raw = data()
    raw["experiment"].update(end_time=0.001, observation_times=[0, 0.00037, 0.001])
    specs = []
    for scale in (0.8, 1, 1.2):
        variant = copy.deepcopy(raw)
        variant["model"]["calcium_channels"][0]["max_permeability_m_per_s"] *= scale
        specs.append(parse_spec(variant))
    cohort = parse_batch(definition(specs, ids=[17, 31, 90]).to_dict())
    full = run_batch(cohort)
    starts = full.checkpoint_at({17: 0.00025, 31: 0.0005, 90: 0.001})
    write_batch_snapshot(tmp_path / "restart", cohort, starts)
    saved = load_batch_snapshot(tmp_path / "restart")
    for world in cohort.worlds:
        same(run(world.simulation).final.state, full.worlds[world.world_id].final.state)
        same(
            run_windowed(world.simulation, WindowPolicy(7)).final.state,
            full.worlds[world.world_id].final.state,
        )
    for width in (1, 2, 3):
        for start in range(0, 3, width):
            part = replace(saved.spec, worlds=saved.spec.worlds[start : start + width])
            result = run_batch_windowed(
                part,
                WindowPolicy(9),
                {w.world_id: saved.checkpoints[w.world_id] for w in part.worlds},
            )
            for world_id, checkpoint in result.checkpoints.items():
                same(checkpoint.state, full.worlds[world_id].final.state)
    changed = specs[1].to_dict()
    changed["experiment"]["calcium_channel_controls"][0]["schedule"].append(
        {"time": 0.0005, "availability": 0.2}
    )
    changed = parse_spec(changed)
    branch = branch_checkpoint(specs[1], starts[31], changed)
    same(run(changed, branch).final.state, run(changed).final.state)
    evidence("replay", {"status": "passed", "widths": [1, 2, 3], "world_ids": [17, 31, 90]})


def test_public_cli(tmp_path):
    raw = data()
    raw["experiment"].update(end_time=0.0001, observation_times=[0, 0.000037, 0.0001])
    path = tmp_path / "input.json"
    path.write_text(json.dumps(raw))
    child = subprocess.run(
        [sys.executable, "-B", "-m", "cells", "run", str(path), "--output", str(tmp_path / "run")],
        capture_output=True,
        text=True,
        check=True,
        timeout=180,
    )
    assert not child.stderr
    saved = load_snapshot(tmp_path / "run/checkpoint_final")
    assert saved.spec.execution.backend == BACKEND and saved.checkpoint.time == 0.0001
    evidence("public-cli", {"status": "passed", "backend": BACKEND})


@pytest.fixture(scope="module")
def coupled():
    spec = parse_assembly(assembly_data())
    state, report = assembly.run(spec, backend=BACKEND)
    evidence("assembly-baseline", report | {"status": "passed"}, flatten(state))
    return spec, state, report


def test_assembly_independent_event_reference(coupled):
    spec, state, _ = coupled
    events = event_histories(spec, state, 0)
    times = sorted({0.0, *(e[0] for rows in events.values() for e in rows)})
    segments = []
    for time in times:
        levels = []
        for b in spec.pools:
            past = [e for e in events[b.cell_id] if e[0] <= time]
            mask, bonds = past[-1][1:3] if past else (b.pool.initial_mask, b.pool.initial_bonds)
            levels.append(
                b.active_availability
                if bonds.bit_count() >= mask.bit_count()
                else b.inactive_availability
            )
        segments.append((time, levels))
    raw = spec.ionic.to_dict()
    expected = reference(raw, [spec.pool.end_time_s], channel_segments=segments)
    errors = compare(
        {k: np.asarray(v)[0:1] for k, v in state.ionic._asdict().items()}, expected, System(raw)
    )
    evidence(
        "assembly-reference",
        {
            "status": "passed",
            "max_errors": errors,
            "event_boundaries": len(times),
            "rhs_calls": expected["rhs_calls"],
        },
    )


def test_assembly_restart_partition_and_transport_effect(coupled, tmp_path):
    spec, state, _ = coupled
    half, _ = assembly.run(spec, backend=BACKEND, until=0.01)
    write_checkpoint(tmp_path / "assembly", spec, half, backend=BACKEND)
    saved, checkpoint, _ = load_checkpoint(tmp_path / "assembly", backend=BACKEND)
    continued, _ = assembly.run(replace(saved, window_ticks=7), backend=BACKEND, state=checkpoint)
    same(continued, state)
    for i in range(spec.pool.worlds):
        raw = spec.to_dict()
        for binding in raw["pools"]:
            binding["pool"].update(worlds=1, world_id_start=spec.pool.world_id_start + i)
        partition, _ = assembly.run(parse_assembly(raw), backend=BACKEND)
        same(partition, jax.tree.map(lambda v, i=i: np.asarray(v)[i : i + 1], state))
    raw = spec.to_dict()
    for control in raw["ionic"]["experiment"]["calcium_channel_controls"]:
        control["schedule"][0]["availability"] = 0
    blocked, _ = assembly.run(parse_assembly(raw), backend=BACKEND)
    same(blocked.pool, state.pool)
    ca = [s.id for s in spec.ionic.model.stores[0].species].index("Ca")
    difference = float(
        np.max(
            np.abs(
                blocked.ionic.chemical_amount_increment[:, :, ca, :]
                - state.ionic.chemical_amount_increment[:, :, ca, :]
            )
        )
    )
    assert difference > 1e-10
    evidence(
        "assembly-replay",
        {"status": "passed", "partition_widths": [1, 2], "calcium_response_fmol": difference},
    )


def test_ensemble_planning_preserves_model_and_world_identity():
    raw = ensemble_definition()
    raw["arms"][0]["definition"] = assembly_data()
    for binding in raw["arms"][0]["definition"]["pools"]:
        for key in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(key, None)
    local, future = plan(raw, 1), jupiter_plan(raw, 4)
    assert local["tasks"] == future["tasks"] and future["deployment"]["maximum_target_gpus"] == 16
    assert not future["deployment"]["remote_execution_qualified"]
    assert all(
        task["definition"]["ionic"]["model"]["id"] == "spatial_calcium@3"
        for task in future["tasks"]
    )


def test_ensemble_aggregation(coupled):
    from cells.ensemble.cluster import aggregate

    _, _, report = coupled
    row = report | {"arm": "cav", "wall_start": 0.0, "wall_end": 1.0}
    summary = aggregate([row, row])["cav"]
    assert summary["physical_model"] == "spatial_calcium@3"
    np.testing.assert_array_equal(
        summary["calcium"]["cytosol_amounts_fmol_sum_over_worlds"],
        2 * np.sum(report["calcium"]["cytosol_amounts_fmol"], axis=0),
    )
    for key in ("gate", "transferred_fmol", "dissipated_energy_pJ"):
        np.testing.assert_array_equal(
            summary["calcium_channels"][key + "_sum_over_worlds"],
            2 * np.sum(report["calcium_channels"][key], axis=0),
        )
    changed = copy.deepcopy(row)
    changed["calcium_channels"]["ids"].reverse()
    with pytest.raises(ValueError, match="owners changed"):
        aggregate([row, changed])
    evidence(
        "ensemble",
        {
            "status": "passed",
            "maximum_planned_gpus": 16,
            "remote_execution_qualified": False,
            "summary": summary,
        },
    )


def test_cpu_gpu_agreement(baseline, coupled):
    if BACKEND != "gpu":
        pytest.skip("CPU baselines retained for subsequent actual L4 comparison")
    target = os.environ.get("CELLS_CAV_EVIDENCE")
    if not target:
        pytest.fail("Use the registered CPU/GPU panel for the complete saved comparison")
    comparisons = {}
    for name, values in [
        ("baseline", baseline.history._asdict()),
        ("assembly-baseline", flatten(coupled[1])),
    ]:
        with np.load(Path(target) / "cpu" / (name + ".npz"), allow_pickle=False) as expected:
            count = 0
            maximum = 0.0
            assert set(expected.files) == set(values)
            for key, a in values.items():
                a = np.asarray(a)
                if a.dtype.kind in "bui":
                    np.testing.assert_array_equal(a, expected[key])
                else:
                    np.testing.assert_allclose(
                        a, expected[key], rtol=3e-10, atol=3e-13, err_msg=key
                    )
                count += a.size
                if a.dtype.kind == "f":
                    maximum = max(maximum, float(np.max(np.abs(a - expected[key]), initial=0)))
        comparisons[name] = {"scalar_values_compared": count, "max_absolute_error": maximum}
    evidence(
        "cpu-gpu", {"status": "passed", "rtol": 3e-10, "atol": 3e-13, "comparisons": comparisons}
    )
