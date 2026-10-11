"""Cross-region calcium/IP3/assembly: owned material, independent physics and replay."""

import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine as assembly
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.batch_windows import iter_batch_windows
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.ensemble.ionic import parse_spec as parse_ensemble
from cells.ensemble.plan import jupiter_plan, plan
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import tissue_calcium as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_checked_step
from tests.unit.test_assembly_cluster import ensemble_definition, event_histories
from tests.unit.test_spatial_calcium import compare, same
from validation.tissue import calcium_fixtures as fixtures
from validation.tissue.calcium_reference import System, physical_energy_derivative, reference

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")


def evidence(name, record, arrays=None):
    if EVIDENCE:
        root = Path(EVIDENCE) / BACKEND
        root.mkdir(parents=True, exist_ok=True)
        (root / (name + ".json")).write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        if arrays is not None:
            np.savez_compressed(root / (name + ".npz"), **arrays)


def initial(raw=None):
    spec = parse_spec(fixtures.definition() if raw is None else raw)
    state, layout = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_versioned_definition_ensemble_and_refinement_grids(backend):
    raw = fixtures.definition(backend=backend)
    spec = parse_spec(raw)
    assert get_model(spec.model) is model
    assert parse_spec(spec.to_dict()) == spec
    assert (
        parse_ensemble({"model": "ionic_worlds@1", "simulation": raw, "worlds": 2}).simulation
        == spec
    )
    for dt in (0.000025, 0.0000125, 0.00000625):
        timeline(parse_spec(raw | {"execution": raw["execution"] | {"dt": dt}}))
    assert model.domain_valid.with_control is model.control_domain_valid


@pytest.mark.parametrize("arm", fixtures.ARMS)
@pytest.mark.parametrize("padded", [False, True])
def test_independent_stage_rates_charge_and_energy(arm, padded):
    raw = fixtures.definition(arm=arm, padded=padded)
    spec, state, p, c = initial(raw)
    rates = model.rhs(state, c, p, p.active, xp=np)
    system = System(raw)
    y = system.initial()
    dy = system.rhs(y, 0.0)
    for k, actual in system.flatten_actual(rates._asdict()).items():
        np.testing.assert_allclose(actual, system.unpack(dy)[k], rtol=3e-11, atol=3e-13, err_msg=k)
    np.testing.assert_allclose(model.chemistry.ownership_residual(rates, p), 0, rtol=0, atol=2e-15)
    np.testing.assert_allclose(
        model.tissue.spatial.component_charge(rates, p, xp=np, derivative=True),
        0,
        rtol=0,
        atol=2e-23,
    )
    work = -1e-3 * np.sum(p.pump_drive * rates.pump_cycles)
    for i in range(len(spec.model.stores)):
        local = model.store_layout(p, i)
        work -= (
            1e-3
            * model.er.processes.chemical_drive(
                model.er.pump_parameters(local), local.temperature, xp=np
            )
            * rates.er_pump_transferred[i, 0]
        )
    work -= 1e-3 * np.sum(
        model.base.base.base.readouts(state, p, xp=np)[-1] * rates.plasma_pump_cycles
    )
    dissipation = sum(np.sum(getattr(rates, k)) for k in rates._fields if "dissipated_energy" in k)
    residual = physical_energy_derivative(system, y, dy) + dissipation - work
    assert abs(residual) < 2e-12


@pytest.mark.parametrize("kind", ["binding", "er_transfer", "ip3_binding"])
def test_internal_chemistry_uses_free_ions_without_charging_plasma(kind):
    spec, state, p, c = initial()
    changed = model.State(*(np.array(v) for v in state))
    names = [s.id for s in spec.model.stores[0].species]
    cy, er = int(p.er_cytosol[0]), int(p.er_er[0])
    ca = names.index("Ca")
    if kind == "binding":
        indices = [names.index(k) for k in ("Ca", "B", "CaB")]
        changed.chemical_amount_increment[0, indices, cy] += 0.0001 * np.array([-1, -1, 1])
    elif kind == "er_transfer":
        changed.chemical_amount_increment[0, ca, [cy, er]] += 0.0001 * np.array([-1, 1])
    else:
        indices = [names.index(k) for k in ("IP3", "IP3_buffer", "IP3_bound")]
        dn = p.er_initial_amount[0, indices[0], cy] / 4
        changed.chemical_amount_increment[0, indices, cy] += dn * np.array([-1, -1, 1])
    assert model.domain_valid(changed, p, p.active, xp=np)
    same(
        model.cell_voltage(state.amount_increment, p, xp=np),
        model.cell_voltage(changed.amount_increment, p, xp=np),
    )
    before, after = (model.rhs(s, c, p, p.active, xp=np) for s in (state, changed))
    if kind == "ip3_binding":
        assert after.er_release_transferred[0, 0] != before.er_release_transferred[0, 0]
        same(after.er_release_transferred[1], before.er_release_transferred[1])
    else:
        assert after.leak_transferred[3, 0] != before.leak_transferred[3, 0]
        assert np.any(
            model.field_values(state, c, p, xp=np).junction_flux_fmol_per_s
            != model.field_values(changed, c, p, xp=np).junction_flux_fmol_per_s
        )
    duplicate = changed._replace(amount_increment=np.array(changed.amount_increment))
    duplicate.amount_increment[3, 0] += 0.0001
    assert not model.domain_valid(duplicate, p, p.active, xp=np)


@pytest.mark.parametrize(
    "fault", ["old_identity", "old_ionic", "solver", "owner", "charge", "off_grid"]
)
def test_inconsistent_meanings_rejected(fault):
    raw = fixtures.definition()
    if fault == "old_identity":
        raw["model"]["id"] = "spatial_calcium@4"
    elif fault == "old_ionic":
        raw["model"]["ionic"]["id"] = "spatial_extracellular@2"
    elif fault == "solver":
        raw["execution"]["field_solver"] = "gauged_dense_kirchhoff@1"
    elif fault == "owner":
        raw["model"]["ionic"]["cells"][1]["membrane"]["outside"] = "missing"
    elif fault == "charge":
        raw["model"]["ionic"]["surroundings"][0]["fixed_charge_equivalent_fmol"] += 0.01
    else:
        raw["experiment"]["observation_times"].insert(1, 0.000037)
    with pytest.raises(ConfigError):
        timeline(parse_spec(raw))


def test_failed_field_rejected_by_composed_stage_guard(monkeypatch):
    _, s, p, c = initial()
    assert model.control_domain_valid(s, c, p, p.active, xp=np)
    monkeypatch.setattr(model.tissue, "field_valid", lambda *args, **kwargs: jnp.asarray(False))
    kept, passed = rk4_checked_step(
        model.rhs,
        model.domain_valid,
        jax.tree.map(jnp.asarray, s),
        1e-5,
        jax.tree.map(jnp.asarray, c),
        jax.tree.map(jnp.asarray, p),
        jnp.asarray(p.active),
    )
    assert not passed
    same(kept, s)


def test_chemical_event_is_an_accepted_observation_boundary():
    raw = fixtures.definition()
    raw["experiment"]["observation_times"].insert(1, 0.000037)
    changes = raw["experiment"]["store_controls"][0]["controls"]
    control = copy.deepcopy(changes[0]) | {"time": 0.000037}
    control["reactions"]["ip3_binding"] = 0.0
    changes.append(control)
    assert 0.000037 in timeline(parse_spec(raw))


@pytest.fixture(scope="module")
def trajectories(tmp_path_factory):
    root = tmp_path_factory.mktemp("tissue-calcium")
    values = {}
    for arm in fixtures.ARMS:
        value = run(parse_spec(fixtures.definition(arm=arm, backend=BACKEND)))
        assert all(v.device.platform == BACKEND for v in value.final.state)
        write_run(root / arm, value, checkpoint_times=(0.001,))
        values[arm] = value
    return values


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_independent_trajectories_and_complete_accounting(arm, trajectories):
    value = trajectories[arm]
    raw = value.spec.to_dict()
    expected = reference(raw, value.observations.times)
    errors = compare(vars(value.observations), expected, System(raw))
    assert value.diagnostics["max_energy_balance_error_pJ"] <= 1e-9
    assert value.diagnostics["max_component_charge_C"] <= 1e-20
    assert value.diagnostics["max_ownership_error_fmol"] <= 2e-11
    assert np.max(value.observations.current_normalized) <= 1
    assert np.any(
        value.observations.ip3_release_fraction[-1] != value.observations.ip3_release_fraction[0]
    )
    if arm == "blocked":
        assert not np.any(value.history.junction_transferred)
        assert np.any(value.history.junction_gate[-1] != value.history.junction_gate[0])
    if arm == "release":
        assert not np.any(
            value.observations.junction_transferred[value.observations.times <= 0.001]
        )
        assert np.any(value.history.junction_transferred[-1])
    evidence(
        "calcium-" + arm,
        {
            "status": "passed",
            "inputs": raw,
            "max_errors": errors,
            "reference_rhs_calls": expected["rhs_calls"],
            "diagnostics": value.diagnostics,
        },
        {
            **{k: np.asarray(v) for k, v in value.history._asdict().items()},
            "plasma_voltage_V": value.observations.plasma_voltage_V,
            **{"reference_" + k: v for k, v in expected.items() if k != "rhs_calls"},
        },
    )


def test_refinement_and_same_region_reduction(trajectories):
    value = trajectories["baseline"]
    raw = value.spec.to_dict()
    system = System(raw)
    expected = reference(raw, value.observations.times)
    errors = []
    for dt in (0.000025, 0.0000125, 0.00000625):
        raw["execution"]["dt"] = dt
        actual = value if dt == 0.0000125 else run(parse_spec(raw))
        compare(vars(actual.observations), expected, system)
        errors.append(
            float(
                np.max(
                    np.abs(
                        system.flatten_actual(vars(actual.observations))[
                            "chemical_amount_increment"
                        ]
                        - expected["chemical_amount_increment"]
                    )
                )
            )
        )
    assert errors[-1] <= max(0.2 * errors[0], 3e-13)
    raw = trajectories["same_region"].spec.to_dict()
    raw["model"]["id"] = "spatial_calcium@4"
    raw["model"]["ionic"]["id"] = "spatial_extracellular@2"
    raw["model"]["ionic"]["closure"]["law"] = "capacitive_components_current_continuity@1"
    raw["execution"]["field_solver"] = "gauged_dense_kirchhoff@1"
    old = run(parse_spec(raw))
    for a, b in zip(old.history, trajectories["same_region"].history, strict=True):
        np.testing.assert_allclose(a, b, rtol=3e-10, atol=3e-13)
    evidence(
        "calcium-refinement",
        {
            "status": "passed",
            "dt_s": [0.000025, 0.0000125, 0.00000625],
            "chemical_errors_fmol": errors,
            "same_region_reduction": "passed",
        },
    )


def test_complete_restart_branch_windows_and_fresh_process(trajectories, tmp_path):
    value = trajectories["baseline"]
    cp = value.checkpoint_at(0.001)
    write_snapshot(tmp_path / "checkpoint", value.spec, cp)
    saved = load_snapshot(tmp_path / "checkpoint")
    same(saved.checkpoint.state, cp.state)
    resumed = run(saved.spec, saved.checkpoint)
    same(resumed.history, model.State(*(v[cp.step_index :] for v in value.history)))
    same(run(value.spec, value.final).final.state, value.final.state)
    raw = value.spec.to_dict()
    changes = raw["experiment"]["store_controls"][0]["controls"]
    modified = copy.deepcopy(changes[0]) | {"time": cp.time}
    modified["reactions"]["ip3_binding"] = 0
    changes.append(modified)
    changed = parse_spec(raw)
    branch = run(changed, branch_checkpoint(value.spec, cp, changed))
    same(branch.final.state, run(changed).final.state)
    assert np.any(
        branch.final.state.er_release_transferred != value.final.state.er_release_transferred
    )
    windows = list(iter_windows(value.spec, WindowPolicy(23, "full"), cp))
    merged = model.State(
        *(
            np.concatenate(
                [getattr(w.history, k)[0 if i == 0 else 1 :] for i, w in enumerate(windows)]
            )
            for k in model.State._fields
        )
    )
    same(merged, resumed.history)
    child = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "cells",
            "resume",
            str(tmp_path / "checkpoint"),
            "--output",
            str(tmp_path / "fresh"),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    (tmp_path / "fresh.stdout.log").write_text(child.stdout)
    (tmp_path / "fresh.stderr.log").write_text(child.stderr)
    child.check_returncode()
    same(load_snapshot(tmp_path / "fresh/checkpoint_final").checkpoint.state, resumed.final.state)
    evidence(
        "calcium-restart",
        {
            "status": "passed",
            "comparison": "bitwise",
            "fresh_process": True,
            "future_ip3_branch": True,
            "terminal_reload": True,
            "changed_windows": True,
        },
    )


def test_world_partition_and_independent_restart(trajectories, tmp_path):
    values = [trajectories[a] for a in ("baseline", "release")]
    batch = BatchSpec(tuple(WorldSpec(i + 10, v.spec) for i, v in enumerate(values)), 2, 324, 2**30)
    result = run_batch(batch)
    for i, value in result.worlds.items():
        same(value.history, values[i - 10].history)
    starts = result.checkpoint_at({10: 0.001, 11: 0.002})
    write_batch_snapshot(tmp_path / "batch", batch, starts)
    saved = load_batch_snapshot(tmp_path / "batch")
    windows = list(iter_batch_windows(saved.spec, WindowPolicy(23, "full"), saved.checkpoints))
    for i in (10, 11):
        parts = [w.worlds[i] for w in windows if i in w.worlds]
        merged = model.State(
            *(
                np.concatenate(
                    [getattr(w.history, k)[0 if j == 0 else 1 :] for j, w in enumerate(parts)]
                )
                for k in model.State._fields
            )
        )
        same(merged, model.State(*(v[starts[i].step_index :] for v in result.worlds[i].history)))
        partition = replace(batch, worlds=(batch.worlds[i - 10],), max_worlds=1)
        same(run_batch(partition).worlds[i].history, result.worlds[i].history)
    evidence(
        "calcium-partition",
        {
            "status": "passed",
            "comparison": "bitwise",
            "world_ids": [10, 11],
            "restart_times": [0.001, 0.002],
        },
    )


@pytest.fixture(scope="module")
def coupled():
    spec = parse_assembly(fixtures.assembly_definition(backend=BACKEND))
    state, report = assembly.run(spec, backend=BACKEND)
    evidence("calcium-assembly", report | {"status": "passed"}, flatten(state))
    return spec, state, report


def test_assembly_event_reference(coupled):
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
    assert len(segments) > 1 and len({tuple(v) for _, v in segments}) > 1
    raw = spec.ionic.to_dict()
    expected = reference(raw, [spec.pool.end_time_s], channel_segments=segments)
    errors = compare(
        {k: np.asarray(v)[0:1] for k, v in state.ionic._asdict().items()}, expected, System(raw)
    )
    evidence(
        "calcium-assembly-reference",
        {
            "status": "passed",
            "max_errors": errors,
            "event_boundaries": len(times),
            "segments": segments,
        },
        {k: v for k, v in expected.items() if k != "rhs_calls"},
    )


def test_assembly_restart_partition_and_ligand_response(coupled, tmp_path):
    spec, state, _ = coupled
    half, _ = assembly.run(spec, backend=BACKEND, until=0.001)
    write_checkpoint(tmp_path / "assembly", spec, half, backend=BACKEND)
    saved, checkpoint, _ = load_checkpoint(tmp_path / "assembly", backend=BACKEND)
    continued, _ = assembly.run(replace(saved, window_ticks=23), backend=BACKEND, state=checkpoint)
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
    reduced, _ = assembly.run(parse_assembly(raw), backend=BACKEND)
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
    evidence(
        "calcium-assembly-replay",
        {
            "status": "passed",
            "comparison": "bitwise",
            "calcium_response_fmol": difference,
            "unchanged_random_events": True,
        },
    )


def test_sixteen_gpu_planning_keeps_worlds_and_model():
    raw = ensemble_definition()
    raw["arms"][0]["definition"] = fixtures.assembly_definition()
    for binding in raw["arms"][0]["definition"]["pools"]:
        for key in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(key, None)
    local, future = plan(raw, 1), jupiter_plan(raw, 4)
    assert local["tasks"] == future["tasks"]
    assert future["deployment"]["maximum_target_gpus"] == 16
    assert not future["deployment"]["remote_execution_qualified"]
    assert all(
        t["definition"]["ionic"]["model"]["id"] == "spatial_calcium@5" for t in future["tasks"]
    )


def test_assembly_aggregation_retains_owned_ligand(coupled):
    from cells.ensemble.cluster import aggregate

    _, _, report = coupled
    row = report | {"arm": "tissue", "wall_start": 0.0, "wall_end": 1.0}
    result = aggregate([row, row])["tissue"]
    assert result["physical_model"] == "spatial_calcium@5"
    for k in ("cytosol_mM", "release_fraction"):
        np.testing.assert_array_equal(
            result["ip3"][k + "_sum_over_worlds"], 2 * np.sum(report["ip3"][k], axis=0)
        )
    missing = dict(row)
    missing.pop("ip3")
    with pytest.raises(ValueError, match="IP3"):
        aggregate([row, missing])


def test_corrupt_owned_inventory_or_energy_rejected(trajectories):
    value = trajectories["baseline"]
    # Match the complete host conversion used by runner and assembly validators.
    host = jax.tree.map(np.asarray, value.final.state)
    model.check_values(host, value.spec)
    for name in ("chemical_amount_increment", "er_transport_dissipated_energy_pJ"):
        corrupted = host._replace(**{name: getattr(host, name) + 0.001})
        with pytest.raises(NumericalError):
            model.check_values(corrupted, value.spec)


def test_cpu_gpu_complete_histories_and_assembly(trajectories, coupled):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU states")
    assert EVIDENCE
    count = 0
    for arm, value in trajectories.items():
        with np.load(
            Path(EVIDENCE) / "cpu" / ("calcium-" + arm + ".npz"), allow_pickle=False
        ) as saved:
            for k, actual in value.history._asdict().items():
                np.testing.assert_allclose(actual, saved[k], rtol=3e-10, atol=3e-13, err_msg=k)
                count += actual.size
            np.testing.assert_allclose(
                value.observations.plasma_voltage_V, saved["plasma_voltage_V"], rtol=0, atol=3e-11
            )
    with np.load(Path(EVIDENCE) / "cpu/calcium-assembly.npz", allow_pickle=False) as saved:
        for k, actual in flatten(coupled[1]).items():
            if np.asarray(actual).dtype.kind in "bui":
                np.testing.assert_array_equal(actual, saved[k], err_msg=k)
            else:
                np.testing.assert_allclose(actual, saved[k], rtol=3e-10, atol=3e-13, err_msg=k)
            count += actual.size
    evidence(
        "calcium-cpu-gpu",
        {
            "status": "passed",
            "complete_state_scalars": count,
            "state_rtol": 3e-10,
            "state_atol": 3e-13,
            "voltage_atol_V": 3e-11,
        },
    )
