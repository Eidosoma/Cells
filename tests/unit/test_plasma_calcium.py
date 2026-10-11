"""PMCA source correspondence and synthetic NCX accounting on CPU and L4."""

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
from cells.core.plasma_calcium_spec import base_spec
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, run_windowed
from cells.ensemble.plan import jupiter_plan, plan
from cells.io import load_snapshot, write_run
from cells.models import plasma_calcium as model
from cells.processes import plasma_calcium as process
from tests.batch_fixtures import definition
from tests.reference_plasma_calcium import (
    F,
    R,
    System,
    native_pmca,
    physical_energy_derivative,
    reference,
    scalar_rates,
)
from tests.unit.test_assembly_cluster import ensemble_definition, event_histories
from tests.unit.test_spatial_calcium import compare, same

ROOT = Path(__file__).resolve().parents[2]
BACKEND = os.environ.get("CELLS_PLASMA_TEST_BACKEND", "cpu")


def data():
    raw = json.loads((ROOT / "configs/plasma_calcium_cluster.json").read_text())
    raw["execution"]["backend"] = BACKEND
    return raw


def assembly_data():
    return json.loads((ROOT / "configs/assembly_regulated_plasma_calcium_cluster.json").read_text())


def evidence(name, record=None, arrays=None):
    target = os.environ.get("CELLS_PLASMA_EVIDENCE")
    if target:
        path = Path(target) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        if record is not None:
            (path / (name + ".json")).write_text(
                json.dumps(record, indent=2, allow_nan=False) + "\n"
            )
        if arrays is not None:
            np.savez_compressed(path / (name + ".npz"), **arrays)


def test_native_pmca_positive_domain_and_explicit_blocker():
    p = process.PumpParameters(0.003, 0.001, 0.5, 1.5, 0.1, 0.1, -10000.0)
    ci = np.array([1e-6, 0.0001, 0.002, 0.002, 0.02, 0.002])
    co = np.array([0.2, 0.1, 0.2, 0.2, 0.01, 0.2])
    v = np.array([-0.12, -0.04, 0.0, 0.12, 0.04, 0.05])
    area = 1e-9
    params = SimpleNamespace(
        deltaGATP=p.delta_g0_J_per_mol,
        cATP=p.atp_mM,
        cADP=p.adp_mM,
        cPi=p.pi_mM,
        R=R,
        F=F,
        KmCa_Ca=p.km_ca_mM,
        KmCa_ATP=p.km_atp_mM,
        alpha_Ca=p.capacity_fmol_per_s * 1e-15 / area,
    )
    native = native_pmca()
    expected = -native(ci.copy(), co.copy(), v, 298.15, params, 1) * area / 1e-15
    # Pinned BETSE ignores its block argument. Our control is an explicit extension.
    np.testing.assert_array_equal(
        -native(ci.copy(), co.copy(), v, 298.15, params, 0) * area / 1e-15, expected
    )
    actual, g, _ = process.pump_rates(ci, co, v, 298.15, p, 1.0, xp=np)
    np.testing.assert_allclose(actual, expected, rtol=3e-12, atol=3e-14)
    assert np.any(actual > 0) and np.any(actual < 0) and np.all(-actual * g >= 0)
    assert np.all(process.pump_rates(ci, co, v, 298.15, p, 0.0, xp=np)[0] == 0)
    with jax.default_device(execution_device(BACKEND)):
        compiled = jax.jit(process.pump_rates)(ci, co, v, 298.15, p, 1.0)
        assert compiled[0].device.platform == BACKEND
        np.testing.assert_allclose(compiled[0], expected, rtol=3e-12, atol=3e-14)
    evidence(
        "native-laws",
        {
            "status": "passed",
            "pump_points": len(ci),
            "native_block_argument_unused": True,
            "scope": (
                "Pinned positive PMCA equation with harmonized constants; no native trajectories"
            ),
        },
        {"pmca_native": expected, "pmca_cells": actual},
    )


def test_ncx_reference_reversal_stoichiometry_and_stall_gradient():
    p = process.ExchangerParameters(0.003, 20.0, 0.001)
    ni, no, ci, co, t = 12.0, 140.0, 0.001, 0.2, 298.15
    reversal = -R * t / F * np.log((ni / no) ** 3 * co / ci)
    v = reversal + np.array([-0.03, 0, 0.03])
    actual, g = process.exchange_rates(ni, no, ci, co, v, t, p, 1.0, xp=np)
    expected = np.array(
        [scalar_rates(ni, no, ci, co, x, t, None, p._asdict(), (1, 1))[1] for x in v]
    )
    np.testing.assert_allclose(actual, expected, rtol=3e-12, atol=3e-17)
    assert actual[0] > 0 > actual[2] and abs(actual[1]) < 1e-17
    assert np.all(-actual * g >= 0)
    assert np.all(process.exchange_rates(ni, no, ci, co, v, t, p, 0.0, xp=np)[0] == 0)
    assert np.all(
        process.exchange_rates(ni, no, ci, co, v, t, p._replace(capacity_fmol_per_s=0), 1.0, xp=np)[
            0
        ]
        == 0
    )
    with jax.default_device(execution_device(BACKEND)):
        compiled = jax.jit(process.exchange_rates)(ni, no, ci, co, v, t, p, 1.0)
        assert compiled[0].device.platform == BACKEND
        np.testing.assert_allclose(compiled[0], expected, rtol=3e-12, atol=3e-17)
        slope = jax.grad(
            lambda voltage: process.exchange_rates(ni, no, ci, co, voltage, t, p, 1.0)[0]
        )(reversal)
        eps = 1e-6
        finite = (
            scalar_rates(ni, no, ci, co, reversal + eps, t, None, p._asdict(), (1, 1))[1]
            - scalar_rates(ni, no, ci, co, reversal - eps, t, None, p._asdict(), (1, 1))[1]
        ) / (2 * eps)
        np.testing.assert_allclose(slope, finite, rtol=2e-9, atol=1e-14)
    evidence(
        "ncx-law",
        {
            "status": "passed",
            "reversal_voltage_V": float(reversal),
            "scope": "Synthetic 3-Na/1-Ca reversible kinetic law; rates uncalibrated",
        },
    )


@pytest.mark.parametrize(
    "case",
    [
        "calcium",
        "sodium",
        "missing_route",
        "duplicate_route",
        "unknown_owner",
        "pump_law",
        "exchanger_law",
        "metabolism",
        "negative_capacity",
        "zero_km",
        "missing_control",
        "duplicate_control",
        "unknown_control",
        "late_start",
        "repeat_time",
        "excess_availability",
        "bool_control",
        "nonfinite",
        "affinity",
        "loss_bound",
    ],
)
def test_invalid_transport_definitions(case):
    raw = data()
    transport = raw["model"]["plasma_transport"]
    routes = transport["membranes"]
    controls = raw["experiment"]["plasma_controls"]
    if case in ("calcium", "sodium"):
        transport[case + "_species"] = "Cl"
    elif case == "missing_route":
        routes.pop()
    elif case == "duplicate_route":
        routes[1] = copy.deepcopy(routes[0])
    elif case == "unknown_owner":
        routes[0]["membrane_id"] = "absent"
    elif case == "pump_law":
        routes[0]["pump"]["law"] = "two_ca_pump"
    elif case == "exchanger_law":
        routes[0]["exchanger"]["law"] = "betse_ncx"
    elif case == "metabolism":
        routes[0]["pump"]["metabolism"] = "finite_atp"
    elif case == "negative_capacity":
        routes[0]["exchanger"]["capacity_fmol_per_s"] = -1
    elif case == "zero_km":
        routes[0]["pump"]["km_ca_mM"] = 0
    elif case == "missing_control":
        controls.pop()
    elif case == "duplicate_control":
        controls[1] = copy.deepcopy(controls[0])
    elif case == "unknown_control":
        controls[0]["membrane_id"] = "absent"
    elif case == "late_start":
        controls[0]["schedule"][0]["time"] = 0.001
    elif case == "repeat_time":
        controls[0]["schedule"] *= 2
    elif case == "excess_availability":
        controls[0]["schedule"][0]["exchanger"] = 1.01
    elif case == "bool_control":
        controls[0]["schedule"][0]["pump"] = True
    elif case == "nonfinite":
        routes[0]["pump"]["atp_mM"] = float("nan")
    elif case == "affinity":
        routes[0]["pump"].update(delta_g0_J_per_mol=100000, atp_mM=1e-9, adp_mM=1000, pi_mM=1000)
    elif case == "loss_bound":
        routes[0]["exchanger"]["capacity_fmol_per_s"] = 1000
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


def test_stage_stoichiometry_owned_scatter_and_energy():
    spec = parse_spec(data())
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0])
    c = type(controls)(*(v[0] for v in controls))
    actual = model.rhs(state, c, p, p.active, xp=np)
    disabled = model.rhs(
        state, c._replace(plasma_pump=0.0, plasma_exchange=0.0), p, p.active, xp=np
    )
    system = System(spec.to_dict())
    y = system.initial()
    dy = system.rhs(y, 0)
    compare(actual._asdict(), system.unpack(dy), system)
    pmca, ncx = actual.plasma_pump_cycles, actual.plasma_exchange_cycles
    delta = actual.amount_increment - disabled.amount_increment
    np.testing.assert_allclose(delta[p.plasma_ca, :2], -(pmca + ncx)[:2], rtol=0, atol=1e-17)
    np.testing.assert_allclose(delta[p.plasma_na, :2], 3 * ncx[:2], rtol=0, atol=1e-17)
    charge = p.valence[:, 0] @ delta
    np.testing.assert_allclose(charge[:2], (-2 * pmca + ncx)[:2], rtol=0, atol=3e-17)
    np.testing.assert_allclose(
        delta.sum(axis=1)
        + (actual.extracellular_amount_increment - disabled.extracellular_amount_increment).sum(
            axis=1
        ),
        0,
        rtol=0,
        atol=2e-14,
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
    work -= 1e-3 * np.sum(model.readouts(state, p, xp=np)[-1] * pmca)
    residual = physical_energy_derivative(system, y, dy) + diss - work
    assert abs(residual) < 2e-12
    evidence(
        "ownership", {"status": "passed", "energy_derivative_residual_pJ_per_s": float(residual)}
    )


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
    raw["model"]["plasma_transport"]["membranes"].reverse()
    raw["experiment"]["plasma_controls"].reverse()
    assert parse_spec(raw) == baseline.spec == parse_spec(baseline.spec.to_dict())
    for key in model.EXTRA_FIELDS:
        assert np.all(getattr(baseline.history, key)[..., 2:] == 0)
    assert np.any(baseline.history.plasma_pump_cycles[-1] > 0)
    assert np.any(baseline.history.plasma_exchange_cycles[-1] > 0)
    summary = write_run(tmp_path / "public", baseline)
    assert summary["model"] == "spatial_calcium@2"
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


@pytest.mark.parametrize(
    "variant", ["pump_off", "exchanger_off", "both_off", "absent", "zero_capacity", "switch"]
)
def test_interventions_and_previous_model_reduction(variant):
    raw = data()
    raw["experiment"].update(end_time=0.001, observation_times=[0, 0.00037, 0.001])
    controls = raw["experiment"]["plasma_controls"]
    if variant in ("pump_off", "exchanger_off", "both_off"):
        for c in controls:
            for key in ("pump", "exchanger"):
                if variant in (key + "_off", "both_off"):
                    c["schedule"][0][key] = 0
    elif variant in ("absent", "zero_capacity"):
        for route in raw["model"]["plasma_transport"]["membranes"]:
            for key in ("pump", "exchanger"):
                if variant == "absent":
                    route[key] = None
                else:
                    route[key]["capacity_fmol_per_s"] = 0
    else:
        controls[0]["schedule"].append({"time": 0.000413, "pump": 0, "exchanger": 0.4})
        controls[1]["schedule"].append({"time": 0.000713, "pump": 0.5, "exchanger": 0})
        er = raw["experiment"]["store_controls"][0]["controls"]
        er.append(copy.deepcopy(er[0]) | {"time": 0.000613, "release": 0})
    result = run(parse_spec(raw))
    if variant in ("both_off", "absent", "zero_capacity"):
        old = run(base_spec(result.spec))
        for field in old.history._fields:
            np.testing.assert_array_equal(
                getattr(result.history, field), getattr(old.history, field)
            )
        assert all(np.all(getattr(result.history, k) == 0) for k in model.EXTRA_FIELDS)
    else:
        canonical = result.spec.to_dict()
        compare(
            vars(result.observations),
            reference(canonical, result.observations.times),
            System(canonical),
        )
        if variant in ("pump_off", "exchanger_off"):
            key = "plasma_pump_cycles" if variant == "pump_off" else "plasma_exchange_cycles"
            assert np.all(getattr(result.history, key) == 0)
    evidence("control-" + variant, {"status": "passed", "diagnostics": result.diagnostics})


def test_complete_restart_windows_partitions_and_future_controls(tmp_path):
    raw = data()
    raw["experiment"].update(end_time=0.001, observation_times=[0, 0.00037, 0.001])
    specs = []
    for scale in (0.8, 1, 1.2):
        variant = copy.deepcopy(raw)
        variant["model"]["plasma_transport"]["membranes"][0]["exchanger"][
            "capacity_fmol_per_s"
        ] *= scale
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
    changed["experiment"]["plasma_controls"][0]["schedule"].append(
        {"time": 0.0005, "pump": 0, "exchanger": 0.2}
    )
    changed = parse_spec(changed)
    branch = branch_checkpoint(specs[1], starts[31], changed)
    same(run(changed, branch).final.state, run(changed).final.state)
    evidence("replay", {"status": "passed", "widths": [1, 2, 3], "world_ids": [17, 31, 90]})


@pytest.mark.parametrize(
    "case", ["pump_cycles", "exchanger_cycles", "dissipation", "negative_dissipation", "padding"]
)
def test_corrupt_complete_checkpoint_is_rejected(baseline, case):
    state = model.State(*(np.array(v) for v in baseline.final.state))
    if case == "pump_cycles":
        state.plasma_pump_cycles[0] += 1e-5
    elif case == "exchanger_cycles":
        state.plasma_exchange_cycles[0] += 1e-5
    elif case == "dissipation":
        state.plasma_dissipated_energy_pJ[0, 0] += 1e-5
    elif case == "negative_dissipation":
        state.plasma_dissipated_energy_pJ[1, 0] = -1e-5
    elif case == "padding":
        state.plasma_exchange_cycles[-1] = 1e-5
    with pytest.raises(NumericalError):
        validate_checkpoint(baseline.spec, replace(baseline.final, state=state))


def test_cubic_dissipation_enclosure_rejects_interior_excursion():
    spec = parse_spec(data())
    state, p = model.initial_values(spec)
    history = model.State(*(np.stack((v, v)) for v in state))
    left = model.State(*(np.zeros_like(v) for v in history))
    right = model.State(*(np.zeros_like(v) for v in history))
    # Valid endpoint inventories/ledgers; endpoint derivatives force an interior peak.
    left.plasma_dissipated_energy_pJ[0, 0, 0] = 1
    right.plasma_dissipated_energy_pJ[1, 0, 0] = -1
    with pytest.raises(NumericalError, match="dissipation"):
        model.check_interpolants(
            np.array([0, 0.001]),
            history,
            model.State(*(v[:-1] for v in left)),
            model.State(*(v[1:] for v in right)),
            p,
        )


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
    for control in raw["ionic"]["experiment"]["plasma_controls"]:
        control["schedule"][0].update(pump=0, exchanger=0)
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
        task["definition"]["ionic"]["model"]["id"] == "spatial_calcium@2"
        for task in future["tasks"]
    )


def test_ensemble_aggregation(coupled):
    from cells.ensemble.cluster import aggregate

    _, _, report = coupled
    row = report | {"arm": "plasma", "wall_start": 0.0, "wall_end": 1.0}
    summary = aggregate([row, row])["plasma"]
    assert summary["physical_model"] == "spatial_calcium@2"
    np.testing.assert_array_equal(
        summary["calcium"]["cytosol_amounts_fmol_sum_over_worlds"],
        2 * np.sum(report["calcium"]["cytosol_amounts_fmol"], axis=0),
    )
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
    target = os.environ.get("CELLS_PLASMA_EVIDENCE")
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
