"""Owned calcium, joint capacitor energy, independent ODEs and assembly replay."""

import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assembly_cell.io import flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import engine as assembly
from cells.assembly_cluster.spec import parse_spec as parse_assembly
from cells.batch_io import load_batch_snapshot, write_batch_snapshot
from cells.core.batch import parse_batch, run_batch
from cells.core.batch_windows import run_batch_windowed
from cells.core.errors import NumericalError
from cells.core.runner import branch_checkpoint, run, timeline, validate_checkpoint
from cells.core.schedule import control_values
from cells.core.spatial_calcium_spec import ionic_spec, store_spec
from cells.core.specs import ConfigError, parse_spec
from cells.core.windows import WindowPolicy, run_windowed
from cells.ensemble.plan import jupiter_plan, plan
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import spatial_calcium as model
from tests.batch_fixtures import definition
from tests.reference_spatial_calcium import System, physical_energy_derivative, reference
from tests.unit.test_assembly_cluster import ensemble_definition, event_histories

ROOT = Path(__file__).resolve().parents[2]
BACKEND = os.environ.get("CELLS_CALCIUM_TEST_BACKEND", "cpu")


def data():
    raw = json.loads((ROOT / "configs/spatial_calcium_cluster.json").read_text())
    raw["execution"]["backend"] = BACKEND
    return raw


def assembly_data():
    return json.loads((ROOT / "configs/assembly_regulated_calcium_cluster.json").read_text())


def evidence(name, record=None, arrays=None):
    target = os.environ.get("CELLS_CALCIUM_EVIDENCE")
    if target:
        path = Path(target) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        if record is not None:
            (path / (name + ".json")).write_text(
                json.dumps(record, indent=2, allow_nan=False) + "\n"
            )
        if arrays is not None:
            np.savez_compressed(path / (name + ".npz"), **arrays)


def same(a, b):
    for x, y in zip(jax.tree.leaves(a), jax.tree.leaves(b), strict=True):
        assert np.asarray(x).dtype == np.asarray(y).dtype
        assert np.asarray(x).shape == np.asarray(y).shape
        assert np.asarray(x).tobytes() == np.asarray(y).tobytes()


def compare(values, expected, system):
    actual = system.flatten_actual(values)
    errors = {}
    for name in actual:
        np.testing.assert_allclose(
            actual[name], expected[name], rtol=3e-9, atol=3e-12, err_msg=name
        )
        errors[name] = float(np.max(np.abs(actual[name] - expected[name]), initial=0))
    return errors


def test_reference_sampling_skips_unobserved_event_intervals():
    raw = data()
    raw["experiment"].update(end_time=0.00015, observation_times=[0, 0.00015])
    segments = [(0.0, [0.0, 1.0]), (0.00004, [1.0, 0.0]), (0.00008, [0.5, 0.5])]
    terminal = reference(raw, [0.00015], channel_segments=segments)
    observed = reference(raw, [0, 0.00004, 0.00008, 0.00015], channel_segments=segments)
    assert terminal["rhs_calls"] == observed["rhs_calls"]
    for name in System(raw).shapes:
        np.testing.assert_array_equal(terminal[name][0], observed[name][-1], err_msg=name)


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


@pytest.mark.parametrize(
    "case",
    [
        "missing_store",
        "duplicate_store",
        "wrong_owner",
        "missing_control",
        "duplicate_control",
        "volume",
        "initial_amount",
        "temperature",
        "standard_state",
        "ionic_species",
        "ion_moiety",
        "species_table",
        "chemical_capacity",
        "reaction_capacity",
        "model_identity",
    ],
)
def test_invalid_ownership_and_chemical_identity(case):
    raw = data()
    stores = raw["model"]["stores"]
    m = stores[0]["model"]
    if case == "missing_store":
        stores.pop()
    elif case == "duplicate_store":
        stores[1] = copy.deepcopy(stores[0])
    elif case == "wrong_owner":
        stores[0]["cell_id"] = "absent"
    elif case == "missing_control":
        raw["experiment"]["store_controls"].pop()
    elif case == "duplicate_control":
        raw["experiment"]["store_controls"][1] = raw["experiment"]["store_controls"][0]
    elif case == "volume":
        m["compartments"][0]["volume_pL"] *= 2
    elif case == "initial_amount":
        m["compartments"][0]["initial_amount_fmol"]["Ca"] *= 2
    elif case == "temperature":
        m["temperature_K"] = 300
    elif case == "standard_state":
        m["standard_concentration_mM"] = 2
    elif case == "ionic_species":
        m["species"][0]["id"] = "unknown"
    elif case == "ion_moiety":
        next(s for s in m["species"] if s["id"] == "K")["moieties"]["B"] = 1
    elif case == "species_table":
        stores[1]["model"]["species"][1]["standard_mu_RT"] += 0.5
    elif case == "chemical_capacity":
        raw["execution"]["chemical_capacity"] = 1
    elif case == "reaction_capacity":
        raw["execution"]["reaction_capacity"] = 1
    elif case == "model_identity":
        raw["model"]["ionic"]["id"] = "other"
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_stage_ownership_nested_capacitors_and_energy():
    spec = parse_spec(data())
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0])
    c = type(controls)(*(v[0] for v in controls))
    actual = model.rhs(state, c, p, p.active, xp=np)
    system = System(spec.to_dict())
    y = system.initial()
    dy = system.rhs(y, 0)
    compare(actual._asdict(), system.unpack(dy), system)
    internal = model.rhs(
        state,
        c._replace(
            membrane=np.zeros_like(c.membrane),
            channel=np.zeros_like(c.channel),
            junction=np.zeros_like(c.junction),
        ),
        p,
        p.active,
        xp=np,
    )
    assert np.all(internal.amount_increment == 0)
    assert np.any(internal.chemical_amount_increment != 0)
    plasma = model.rhs(
        state,
        c._replace(
            er_reactions=np.zeros_like(c.er_reactions),
            er_passive=np.zeros_like(c.er_passive),
            er_pump=np.zeros_like(c.er_pump),
            er_release=np.zeros_like(c.er_release),
        ),
        p,
        p.active,
        xp=np,
    )
    for i in range(2):
        s, local = model.store_state(plasma, i), model.store_layout(p, i)
        assert np.all(s.amount_increment[:, local.er] == 0)
        charge = p.chemical_fixed_charge_C[i] + model.CHARGE_PER_FMOL * (
            local.valence @ (local.initial_amount * local.active)
        )
        target = local.capacitance * local.initial_voltage * local.incidence
        target[local.cytosol] += p.capacitance[p.cell_membranes[i]] * p.voltage_reference[i]
        np.testing.assert_allclose(charge, target, rtol=0, atol=3e-24)
    dissipation = sum(
        np.sum(getattr(actual, name))
        for name in (
            "dissipated_energy_pJ",
            "junction_dissipated_energy_pJ",
            "face_dissipated_energy_pJ",
            "reaction_dissipated_energy_pJ",
            "er_transport_dissipated_energy_pJ",
        )
    )
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
    assert abs(physical_energy_derivative(system, y, dy) + dissipation - work) < 2e-12
    with pytest.raises(ConfigError, match="50 us"):
        timeline(replace(spec, execution=replace(spec.execution, dt=0.0001)))
    evidence(
        "ownership",
        {
            "status": "passed",
            "energy_derivative_residual_pJ_per_s": float(
                physical_energy_derivative(system, y, dy) + dissipation - work
            ),
        },
    )


def test_canonical_schema_and_complete_public_artifacts(baseline, tmp_path):
    raw = data()
    raw["model"]["stores"].reverse()
    raw["experiment"]["store_controls"].reverse()
    for store in raw["model"]["stores"]:
        for field in ("species", "moieties", "reactions", "compartments"):
            store["model"][field].reverse()
    assert parse_spec(raw) == baseline.spec == parse_spec(baseline.spec.to_dict())
    assert np.all(baseline.history.chemical_amount_increment[..., 2] == 0)
    write_run(tmp_path / "public", baseline)
    saved = load_snapshot(tmp_path / "public/checkpoint_final")
    same(saved.checkpoint.state, baseline.final.state)
    same(saved.checkpoint.layout, baseline.final.layout)


def test_independent_full_state_references_and_refinement(baseline):
    raw = baseline.spec.to_dict()
    system = System(raw)
    references = [
        reference(raw, baseline.observations.times, method=m) for m in ("DOP853", "Radau")
    ]
    errors = {}
    for method, expected in zip(("DOP853", "Radau"), references, strict=True):
        errors[method] = compare(vars(baseline.observations), expected, system)
        evidence(
            "reference-" + method,
            {"rhs_calls": expected["rhs_calls"]},
            {k: v for k, v in expected.items() if k != "rhs_calls"},
        )
    for name in system.shapes:
        np.testing.assert_allclose(
            references[0][name], references[1][name], rtol=2e-10, atol=5e-14, err_msg=name
        )
    convergence = []
    for dt in (0.000025, 0.0000125, 0.00000625):
        raw["execution"]["dt"] = dt
        result = baseline if dt == 0.0000125 else run(parse_spec(raw))
        actual = system.flatten_actual(vars(result.observations))["chemical_amount_increment"]
        convergence.append(
            float(np.max(np.abs(actual - references[0]["chemical_amount_increment"])))
        )
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
    "variant", ["plasma_ca_off", "release_switch", "internal_off", "external_off"]
)
def test_interventions_and_component_reductions(baseline, variant):
    raw = data()
    if variant in ("plasma_ca_off", "external_off"):
        for m in raw["experiment"]["membrane_controls"]:
            if variant == "external_off":
                m["leak"][0]["multipliers"] = dict.fromkeys(m["leak"][0]["multipliers"], 0)
                m["pump"][0]["multiplier"] = 0
            else:
                m["leak"][0]["multipliers"]["Ca"] = 0
    if variant == "external_off":
        for k, f in [("channel", "availability"), ("junction", "open_fraction")]:
            for c in raw["experiment"][k + "_controls"]:
                c["schedule"][0][f] = 0
    if variant == "internal_off":
        for s in raw["experiment"]["store_controls"]:
            c = s["controls"][0]
            c.update(
                reactions=dict.fromkeys(c["reactions"], 0),
                passive=dict.fromkeys(c["passive"], 0),
                pump=0,
                release=0,
            )
    if variant == "release_switch":
        controls = raw["experiment"]["store_controls"][0]["controls"]
        controls[0]["release"] = 0
        controls.append(copy.deepcopy(controls[0]) | {"time": 0.00613, "release": 1})
    result = run(parse_spec(raw))
    canonical = result.spec.to_dict()
    if variant == "internal_off":
        old = run(ionic_spec(result.spec))
        for field in old.history._fields:
            np.testing.assert_allclose(
                getattr(result.history, field), getattr(old.history, field), rtol=2e-12, atol=3e-13
            )
    elif variant == "external_off":
        for i in range(2):
            old = run(store_spec(result.spec, i))
            for actual, expected in zip(
                model.store_state(result.history, i), old.history, strict=True
            ):
                np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=3e-13)
    else:
        compare(
            vars(result.observations),
            reference(canonical, result.observations.times),
            System(canonical),
        )
        assert not np.array_equal(
            result.history.chemical_amount_increment[-1],
            baseline.history.chemical_amount_increment[-1],
        )
    evidence("control-" + variant, {"status": "passed", "diagnostics": result.diagnostics})


def test_complete_restart_windows_partitions_and_future_branch(tmp_path):
    raw = data()
    raw["experiment"].update(end_time=0.001, observation_times=[0, 0.00037, 0.001])
    specs = []
    for scale in (0.8, 1, 1.2):
        variant = copy.deepcopy(raw)
        variant["model"]["stores"][0]["model"]["membrane"]["pump"]["capacity_fmol_per_s"] *= scale
        specs.append(parse_spec(variant))
    cohort = parse_batch(definition(specs, ids=[17, 31, 90]).to_dict())
    full = run_batch(cohort)
    starts = full.checkpoint_at({17: 0.00025, 31: 0.0005, 90: 0.001})
    write_batch_snapshot(tmp_path / "restart", cohort, starts)
    saved = load_batch_snapshot(tmp_path / "restart")
    endpoints = {}
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
                endpoints.update(
                    {
                        f"width_{width}_world_{world_id}_{k}": np.asarray(v)
                        for k, v in checkpoint.state._asdict().items()
                    }
                )
    changed = specs[1].to_dict()
    control = copy.deepcopy(changed["experiment"]["store_controls"][0]["controls"][0])
    changed["experiment"]["store_controls"][0]["controls"].append(
        control | {"time": 0.0005, "pump": 0}
    )
    changed = parse_spec(changed)
    branch = branch_checkpoint(specs[1], starts[31], changed)
    same(run(changed, branch).final.state, run(changed).final.state)
    evidence(
        "replay", {"status": "passed", "widths": [1, 2, 3], "world_ids": [17, 31, 90]}, endpoints
    )


def test_corrupt_ownership_energy_and_complete_checkpoint(baseline, tmp_path):
    for case in ("ownership", "energy"):
        state = model.State(*(np.array(v) for v in baseline.final.state))
        if case == "ownership":
            state.chemical_amount_increment[0, 1, 0] += 1e-7
        else:
            state.er_transport_dissipated_energy_pJ[0, 0] += 1e-5
        with pytest.raises(NumericalError):
            validate_checkpoint(baseline.spec, replace(baseline.final, state=state))
    write_snapshot(tmp_path / "corrupt", baseline.spec, baseline.final)
    with (tmp_path / "corrupt/state.npz").open("ab") as stream:
        stream.write(b"corrupt")
    with pytest.raises(ConfigError, match="checksum"):
        load_snapshot(tmp_path / "corrupt")


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
    spec, state, report = coupled
    events = event_histories(spec, state, 0)
    times = sorted({0.0, *(e[0] for rows in events.values() for e in rows)})
    segments = []
    exposure = np.zeros(len(spec.pools))
    for time in times:
        opening = []
        for b in spec.pools:
            past = [e for e in events[b.cell_id] if e[0] <= time]
            mask, bonds = past[-1][1:3] if past else (b.pool.initial_mask, b.pool.initial_bonds)
            opening.append(
                b.active_availability
                if bonds.bit_count() >= mask.bit_count()
                else b.inactive_availability
            )
        segments.append((time, opening))
    for (start, levels), end in zip(segments, [*times[1:], spec.pool.end_time_s], strict=True):
        exposure += np.asarray(levels) * (end - start)
    raw = spec.ionic.to_dict()
    expected = reference(raw, [spec.pool.end_time_s], channel_segments=segments)
    errors = compare(
        {k: np.asarray(v)[0:1] for k, v in state.ionic._asdict().items()}, expected, System(raw)
    )
    np.testing.assert_allclose(state.availability_exposure_s[0], exposure, rtol=0, atol=3e-16)
    assert report["calcium"]["er_voltage_V"]
    evidence(
        "assembly-reference",
        {
            "status": "passed",
            "max_errors": errors,
            "event_boundaries": len(times),
            "rhs_calls": expected["rhs_calls"],
        },
    )


def test_assembly_complete_restart_partition_and_channel_effect(coupled, tmp_path):
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
    for binding in raw["pools"]:
        binding["coupling"].update(inactive_availability=0, active_availability=0)
    closed, _ = assembly.run(parse_assembly(raw), backend=BACKEND)
    same(closed.pool, state.pool)
    calcium = [s.id for s in spec.ionic.model.stores[0].species].index("Ca")
    difference = np.max(
        np.abs(
            closed.ionic.chemical_amount_increment[:, :, calcium, :]
            - state.ionic.chemical_amount_increment[:, :, calcium, :]
        )
    )
    assert difference > 1e-12
    evidence(
        "assembly-replay",
        {
            "status": "passed",
            "partition_widths": [1, 2],
            "calcium_response_fmol": float(difference),
        },
    )


def test_ensemble_planning_preserves_calcium_and_world_identity():
    raw = ensemble_definition()
    raw["arms"][0]["definition"] = assembly_data()
    for binding in raw["arms"][0]["definition"]["pools"]:
        for key in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(key, None)
    local, future = plan(raw, 1), jupiter_plan(raw, 4)
    assert local["tasks"] == future["tasks"] and future["deployment"]["maximum_target_gpus"] == 16
    assert not future["deployment"]["remote_execution_qualified"]
    assert all(
        task["definition"]["ionic"]["model"]["id"] == "spatial_calcium@1"
        for task in future["tasks"]
    )


def test_assembly_ensemble_calcium_aggregation(coupled):
    from cells.ensemble.cluster import aggregate

    _, _, report = coupled
    row = report | {"arm": "calcium", "wall_start": 0.0, "wall_end": 1.0}
    summary = aggregate([row, row])["calcium"]
    assert summary["physical_model"] == "spatial_calcium@1"
    for key in ("cytosol_amounts_fmol", "er_voltage_V"):
        np.testing.assert_array_equal(
            summary["calcium"][key + "_sum_over_worlds"],
            2 * np.sum(report["calcium"][key], axis=0),
        )
    with pytest.raises(ValueError, match="owners"):
        aggregate([row, row | {"physical_model": "spatial_extracellular@2"}])
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
    target = os.environ.get("CELLS_CALCIUM_EVIDENCE")
    if not target:
        pytest.fail("Run the registered CPU/GPU panel to compare complete saved baselines")
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
