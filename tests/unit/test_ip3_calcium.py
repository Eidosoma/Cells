"""Owned finite IP3 chemistry, native release factors and complete CPU/L4 replay."""

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
from cells.core.ip3_calcium_spec import base_spec
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, run_windowed
from cells.ensemble.plan import jupiter_plan, plan
from cells.io import load_snapshot, write_run
from cells.models import ip3_calcium as model
from cells.processes import ip3_release as process
from tests.batch_fixtures import definition
from tests.reference_ip3_calcium import (
    System,
    native_functions,
    physical_energy_derivative,
    reference,
)
from tests.unit.test_assembly_cluster import ensemble_definition, event_histories
from tests.unit.test_spatial_calcium import compare, same

ROOT = Path(__file__).resolve().parents[2]
BACKEND = os.environ.get("CELLS_IP3_TEST_BACKEND", "cpu")


def data():
    raw = json.loads((ROOT / "configs/ip3_calcium_cluster.json").read_text())
    raw["execution"]["backend"] = BACKEND
    return raw


def assembly_data():
    return json.loads((ROOT / "configs/assembly_regulated_ip3_calcium_cluster.json").read_text())


def evidence(name, record=None, arrays=None):
    target = os.environ.get("CELLS_IP3_EVIDENCE")
    if target:
        path = Path(target) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        if record is not None:
            (path / (name + ".json")).write_text(
                json.dumps(record, indent=2, allow_nan=False) + "\n"
            )
        if arrays is not None:
            np.savez_compressed(path / (name + ".npz"), **arrays)


def test_native_ip3_network_branches_units_powers_and_device():
    native = native_functions()["channels"]
    c = np.array([0, 1e-10, 0.00003, 0.00015, 0.001, 1.0])
    calcium = np.array([0.0001, 0.0003, 0.001, 0.003, 0.01, 0.1])
    p = SimpleNamespace(
        act_Km_Ca=0.001,
        act_n_Ca=2,
        inh_Km_Ca=0.01,
        inh_n_Ca=2,
        act_Km_IP3=0.00015,
        act_n_IP3=2,
        max_er=7e-7,
    )
    ca_factor = (calcium / p.act_Km_Ca) ** 2 / (1 + (calcium / p.act_Km_Ca) ** 2)
    ca_factor /= 1 + (calcium / p.inh_Km_Ca) ** 2
    branches = ("molecules", "metabo", "grn", "priority", "missing", "absent")
    for power in (1, 2, 4, 8):
        p.act_n_IP3 = power
        factor = np.asarray(process.open_fraction(c, p.act_Km_IP3, power, xp=np))
        direct = (c / p.act_Km_IP3) ** power
        np.testing.assert_allclose(factor, direct / (1 + direct), rtol=3e-14, atol=3e-16)
        for branch in branches:
            sim = SimpleNamespace(
                iCa=0, cc_cells=calcium[None, :], cdl=len(c), molecules=None, metabo=None, grn=None
            )
            mol = SimpleNamespace(molecules={"IP3": object()}, cell_concs={"IP3": c})
            network = SimpleNamespace(core=SimpleNamespace(cell_concs={"IP3": c}))
            if branch == "molecules":
                sim.molecules = mol
            elif branch in ("metabo", "grn"):
                # Empty higher-priority sources must fall through to the named network.
                sim.molecules = SimpleNamespace(molecules={}, cell_concs={})
                if branch == "grn":
                    sim.metabo = SimpleNamespace(core=SimpleNamespace(cell_concs={}))
                setattr(sim, branch, network)
            elif branch == "priority":
                sim.molecules = mol
                sim.metabo = SimpleNamespace(core=SimpleNamespace(cell_concs={"IP3": c * 9}))
                sim.grn = SimpleNamespace(core=SimpleNamespace(cell_concs={"IP3": c * 17}))
            elif branch == "missing":
                sim.grn = SimpleNamespace(core=SimpleNamespace(cell_concs={}))
            er = SimpleNamespace(
                Dm_channels=np.zeros((1, len(c))), Dm_er_base=np.full((1, len(c)), 2e-8)
            )
            native(er, sim, None, p)
            expected = ca_factor * (
                1 if branch == "absent" else 0 if branch == "missing" else factor
            )
            np.testing.assert_allclose(
                er.Dm_channels[0], p.max_er * expected, rtol=3e-14, atol=3e-22
            )
            np.testing.assert_array_equal(er.Dm_er, er.Dm_er_base + er.Dm_channels)
        with jax.default_device(execution_device(BACKEND)):
            actual = jax.jit(process.open_fraction)(c, p.act_Km_IP3, power)
            assert actual.device.platform == BACKEND
            np.testing.assert_allclose(actual, factor, rtol=3e-14, atol=3e-16)
    with jax.default_device(execution_device(BACKEND)):
        derivative = jax.grad(lambda x: process.open_fraction(x, 0.00015, 2))(0.00015)
        np.testing.assert_allclose(derivative, 2 / (4 * 0.00015), rtol=3e-14)
    extreme = process.open_fraction(np.array([0, 1e-300, 1e300, -1, np.nan]), 1e-12, 8, xp=np)
    np.testing.assert_array_equal(extreme[:3], [0, 0, 1])
    assert np.all(np.isnan(extreme[3:]))
    evidence(
        "native-laws",
        {
            "status": "passed",
            "network_branches": list(branches),
            "powers": [1, 2, 4, 8],
            "concentration_unit": "mM",
            "backend": BACKEND,
        },
    )


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "duplicate",
        "unknown_owner",
        "species",
        "law",
        "not_free",
        "no_release",
        "zero_km",
        "negative_km",
        "nan_km",
        "bool_km",
        "zero_power",
        "fractional_power",
        "bool_power",
        "large_power",
        "old_identity",
    ],
)
def test_invalid_ip3_definitions(case):
    raw = data()
    rows = raw["model"]["ip3_release"]
    if case == "missing":
        rows.pop()
    elif case == "duplicate":
        rows[1] = copy.deepcopy(rows[0])
    elif case == "unknown_owner":
        rows[0]["cell_id"] = "absent"
    elif case == "species":
        rows[0]["species_id"] = "IP3_bound"
    elif case == "law":
        rows[0]["law"] = "unknown@1"
    elif case == "not_free":
        for store in raw["model"]["stores"]:
            next(s for s in store["model"]["species"] if s["id"] == "IP3")["moieties"][
                "IP3_site"
            ] = 1
    elif case == "no_release":
        raw["model"]["stores"][0]["model"]["membrane"]["release"] = None
        raw["experiment"]["store_controls"][0]["controls"][0]["release"] = 0
    elif case.endswith("km"):
        rows[0]["activation_mM"] = {
            "zero_km": 0,
            "negative_km": -1,
            "nan_km": np.nan,
            "bool_km": True,
        }[case]
    elif case.endswith("power"):
        rows[0]["activation_n"] = {
            "zero_power": 0,
            "fractional_power": 1.5,
            "bool_power": True,
            "large_power": 9,
        }[case]
    else:
        raw["model"]["id"] = "spatial_calcium@3"
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


def test_stage_owned_ip3_independent_derivative_and_energy():
    spec = parse_spec(data())
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0])
    c = type(controls)(*(v[0] for v in controls))
    system = System(spec.to_dict())
    y = system.initial()
    actual = model.rhs(state, c, p, p.active, xp=np)
    dy = system.rhs(y, 0.0)
    for key, value in system.flatten_actual(actual._asdict()).items():
        np.testing.assert_allclose(
            value, system.unpack(dy)[key], rtol=3e-11, atol=3e-13, err_msg=key
        )
    diss = sum(np.sum(getattr(actual, k)) for k in actual._fields if "dissipated_energy" in k)
    work = -1e-3 * np.sum(p.pump_drive * actual.pump_cycles)
    for i in range(len(spec.model.stores)):
        local = model.store_layout(p, i)
        work -= (
            1e-3
            * model.er.processes.chemical_drive(
                model.er.pump_parameters(local), local.temperature, xp=np
            )
            * actual.er_pump_transferred[i, 0]
        )
    work -= 1e-3 * np.sum(model.base.base.readouts(state, p, xp=np)[-1] * actual.plasma_pump_cycles)
    residual = physical_energy_derivative(system, y, dy) + diss - work
    assert abs(residual) < 2e-12
    ids = [s.id for s in spec.model.stores[0].species]
    indices = [ids.index(k) for k in ("IP3", "IP3_buffer", "IP3_bound")]
    ip3 = indices[0]
    disabled = model.rhs(state, c._replace(er_release=0.0), p, p.active, xp=np)
    np.testing.assert_array_equal(
        actual.chemical_amount_increment[:, indices, :],
        disabled.chemical_amount_increment[:, indices, :],
    )
    for i, store in enumerate(spec.model.stores):
        local = model.store_layout(p, i)
        moiety_rates = local.moieties @ actual.chemical_amount_increment[i]
        for name in ("IP3", "IP3_site"):
            np.testing.assert_allclose(
                moiety_rates[store.moieties.index(name)], 0, rtol=0, atol=3e-18
            )
    # Unbind ligand in only cell 0 without changing either moiety total or charge.
    changed = model.State(*(np.array(v) for v in state))
    cy = p.er_cytosol[0]
    dn = p.er_initial_amount[0, ip3, cy] / 4
    changed.chemical_amount_increment[0, indices, cy] += dn * np.array([1, 1, -1])
    a, b = system.offsets[:2]
    system.stores[0].unpack(y[a:b])[0][indices, system.stores[0].cy] += dn * np.array([1, 1, -1])
    altered = model.rhs(changed, c, p, p.active, xp=np)
    expected = system.unpack(system.rhs(y, 0.0))
    for key, value in system.flatten_actual(altered._asdict()).items():
        np.testing.assert_allclose(value, expected[key], rtol=3e-11, atol=3e-13, err_msg=key)
    before, after = (model.ip3_readouts(s, p, xp=np)[1] for s in (state, changed))
    assert after[0] > before[0] and after[1] == before[1]
    assert altered.er_release_transferred[0, 0] != actual.er_release_transferred[0, 0]
    np.testing.assert_array_equal(
        altered.er_release_transferred[1], actual.er_release_transferred[1]
    )
    other = model.State(*(np.array(v) for v in state))
    er = model.store_layout(p, 0).er
    other.chemical_amount_increment[0, indices, er] += dn * np.array([1, 1, -1])
    np.testing.assert_array_equal(
        model.ip3_readouts(other, p, xp=np), model.ip3_readouts(state, p, xp=np)
    )
    evidence(
        "ownership",
        {
            "status": "passed",
            "energy_derivative_residual_pJ_per_s": float(residual),
            "initial_release_fraction": before.tolist(),
            "changed_release_fraction": after.tolist(),
        },
    )


@pytest.mark.parametrize("variant", ["blocked", "binding_off", "switch"])
def test_release_and_ligand_interventions(variant):
    raw = data()
    raw["experiment"].update(end_time=0.001, observation_times=[0, 0.00037, 0.001])
    for row in raw["experiment"]["store_controls"]:
        ctrl = row["controls"][0]
        if variant == "blocked":
            ctrl["release"] = 0
        elif variant == "binding_off":
            ctrl["reactions"]["ip3_binding"] = 0
    if variant == "switch":
        changes = raw["experiment"]["store_controls"][0]["controls"]
        next_control = copy.deepcopy(changes[0]) | {"time": 0.000413}
        next_control["reactions"]["ip3_binding"] = 0
        changes.append(next_control)
        changes.append(copy.deepcopy(next_control) | {"time": 0.000713, "release": 0})
    result = run(parse_spec(raw))
    if variant == "blocked":
        old = run(base_spec(result.spec))
        same(result.history, old.history)
        assert np.all(result.history.er_release_transferred == 0)
    elif variant == "binding_off":
        c = result.observations.ip3_cytosol_mM
        np.testing.assert_array_equal(c, np.broadcast_to(c[0], c.shape))
    canonical = result.spec.to_dict()
    errors = compare(
        vars(result.observations),
        reference(canonical, result.observations.times),
        System(canonical),
    )
    evidence(
        "control-" + variant,
        {"status": "passed", "diagnostics": result.diagnostics, "max_errors": errors},
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


def test_canonical_schema_observations_and_complete_artifacts(baseline, tmp_path):
    raw = data()
    raw["model"]["ip3_release"].reverse()
    assert parse_spec(raw) == baseline.spec == parse_spec(baseline.spec.to_dict())
    system = System(baseline.spec.to_dict())
    amounts = system.flatten_actual(vars(baseline.observations))["chemical_amount_increment"]
    expected = np.stack(
        [
            (s.n0[s.ip3, s.cy] + amounts[:, i, s.ip3, s.cy]) / s.volume[s.cy]
            for i, s in enumerate(system.stores)
        ],
        axis=-1,
    )
    np.testing.assert_allclose(baseline.observations.ip3_cytosol_mM, expected, rtol=2e-15, atol=0)
    assert np.all(expected[-1] < expected[0])
    read_only = replace(
        baseline.spec, experiment=replace(baseline.spec.experiment, observation_times=(0.0, 0.02))
    )
    same(run(read_only).history, baseline.history)
    summary = write_run(tmp_path / "public", baseline)
    assert summary["model"] == "spatial_calcium@4" and summary["ip3_release_law"] == process.LAW_ID
    saved = load_snapshot(tmp_path / "public/checkpoint_final")
    same(saved.checkpoint.state, baseline.final.state)
    same(saved.checkpoint.layout, baseline.final.layout)


@pytest.mark.parametrize("case", ["negative", "moiety", "cross_cell", "parameter"])
def test_corrupt_ip3_checkpoint_rejected(baseline, case):
    state = model.State(*(np.array(v) for v in baseline.final.state))
    p = baseline.final.layout
    ids = [s.id for s in baseline.spec.model.stores[0].species]
    ip3, cy = ids.index("IP3"), int(p.er_cytosol[0])
    checkpoint = replace(baseline.final, state=state)
    if case == "negative":
        state.chemical_amount_increment[0, ip3, cy] = -2 * p.er_initial_amount[0, ip3, cy]
    elif case in ("moiety", "cross_cell"):
        state.chemical_amount_increment[0, ip3, cy] += 1e-6
        if case == "cross_cell":
            state.chemical_amount_increment[1, ip3, int(p.er_cytosol[1])] -= 1e-6
    else:
        checkpoint = replace(
            checkpoint, layout=p._replace(ip3_activation=np.asarray(p.ip3_activation) * 2)
        )
    with pytest.raises(ConfigError if case == "parameter" else NumericalError):
        validate_checkpoint(baseline.spec, checkpoint)


def test_ip3_cubic_rejects_interior_negative_inventory():
    spec = parse_spec(data())
    state, p = model.initial_values(spec)
    history = model.State(*(np.stack((v, v)) for v in state))
    left = model.State(*(np.zeros_like(v[:1]) for v in history))
    right = model.State(*(np.zeros_like(v[:1]) for v in history))
    ip3 = [s.id for s in spec.model.stores[0].species].index("IP3")
    left.chemical_amount_increment[0, 0, ip3, p.er_cytosol[0]] = -1e5
    right.chemical_amount_increment[0, 0, ip3, p.er_cytosol[0]] = 1e5
    with pytest.raises(NumericalError):
        model.check_interpolants(np.array([0, 0.001]), history, left, right, p)


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
        variant["model"]["ip3_release"][0]["activation_mM"] *= scale
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
    changes = changed["experiment"]["store_controls"][0]["controls"]
    control = copy.deepcopy(changes[0]) | {"time": 0.0005}
    control["reactions"]["ip3_binding"] = 0
    changes.append(control)
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


def test_assembly_restart_partition_and_ip3_response(coupled, tmp_path):
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
    for binding in raw["ionic"]["model"]["ip3_release"]:
        binding["activation_mM"] *= 10
    reduced, report = assembly.run(parse_assembly(raw), backend=BACKEND)
    same(reduced.pool, state.pool)
    ca = [s.id for s in spec.ionic.model.stores[0].species].index("Ca")
    difference = float(
        np.max(
            np.abs(
                reduced.ionic.chemical_amount_increment[:, :, ca, :]
                - state.ionic.chemical_amount_increment[:, :, ca, :]
            )
        )
    )
    assert difference > 1e-10
    assert np.all(np.asarray(report["ip3"]["release_fraction"]) < 0.02)
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
        task["definition"]["ionic"]["model"]["id"] == "spatial_calcium@4"
        for task in future["tasks"]
    )


def test_ensemble_aggregation(coupled):
    from cells.ensemble.cluster import aggregate

    _, _, report = coupled
    row = report | {"arm": "ip3", "wall_start": 0.0, "wall_end": 1.0}
    summary = aggregate([row, row])["ip3"]
    assert summary["physical_model"] == "spatial_calcium@4"
    for key in ("cytosol_mM", "release_fraction"):
        np.testing.assert_array_equal(
            summary["ip3"][key + "_sum_over_worlds"], 2 * np.sum(report["ip3"][key], axis=0)
        )
    for case in ("owners", "shape", "law", "missing", "domain"):
        changed = copy.deepcopy(row)
        if case == "owners":
            changed["ip3"]["cell_ids"].reverse()
        elif case == "shape":
            changed["ip3"]["release_fraction"] = np.asarray(changed["ip3"]["release_fraction"])[
                :, :1
            ].tolist()
        elif case == "law":
            changed["ip3"]["law"] = "unknown@1"
        elif case == "missing":
            changed.pop("ip3")
        else:
            changed["ip3"]["release_fraction"][0][0] = 1.1
        with pytest.raises(ValueError, match="IP3"):
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
    target = os.environ.get("CELLS_IP3_EVIDENCE")
    if not target:
        pytest.fail("Use the registered CPU/GPU panel for the complete saved comparison")
    comparisons = {}
    for name, values in [
        ("baseline", baseline.history._asdict()),
        ("assembly-baseline", flatten(coupled[1])),
    ]:
        with np.load(Path(target) / "cpu" / (name + ".npz"), allow_pickle=False) as expected:
            count, maximum = 0, 0.0
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
