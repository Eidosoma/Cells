"""Integrated scheduled injury: owner checks, independent rates and complete replay."""

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assembly.spec import AssemblyError
from cells.assembly_cell.io import clock_identity, flatten, load_checkpoint, write_checkpoint
from cells.assembly_cluster import controls, engine
from cells.assembly_cluster.spec import channel_owners, parse_spec
from cells.core.errors import NumericalError
from cells.core.schedule import control_values
from cells.ensemble.cluster import aggregate
from cells.ensemble.families import bind_definition
from cells.ensemble.plan import jupiter_plan, plan
from cells.models import surface_repair as model
from tests.unit.test_assembly_cluster import ensemble_definition, event_histories, same
from tests.unit.test_surface_calcium import BACKEND, EVIDENCE, evidence
from tests.unit.test_surface_kinetic import assert_states
from tests.unit.test_surface_repair_full import compare_backend, normalized
from validation.tissue import surface_calcium_cav_fixtures as previous
from validation.tissue import surface_repair_fixtures as fixtures
from validation.tissue import surface_repair_reference as reference


def test_schedule_roundtrip_boundaries_and_all_control_owners():
    raw = fixtures.assembly_definition()
    first = raw["ionic"]["experiment"]["channel_controls"][0]["schedule"]
    first.append(dict(time=5.3e-6, availability=0.0))
    spec = parse_spec(raw)
    assert parse_spec(spec.to_dict()).fingerprint == spec.fingerprint
    table = controls.prepare(spec.ionic)
    assert isinstance(table, controls.ScheduledControl)
    assert controls.extra_boundaries(spec.ionic) == 2
    np.testing.assert_array_equal(table.times[:-1], [0.0, 5.3e-6, 15.3e-6])
    assert np.isinf(table.times[-1])
    jax.config.update("jax_enable_x64", True)
    at = jax.jit(controls.at)
    for time in (0.0, np.nextafter(5.3e-6, 0.0), 5.3e-6, 15.3e-6, 50e-6):
        selected, next_time = at(table, time)
        expected = control_values(spec.ionic, [time])
        for a, b in zip(selected, expected, strict=True):
            np.testing.assert_array_equal(a, b[0])
        assert next_time > time
    assert at(table, 5.3e-6)[0].injury[0] == 1
    assert at(table, 5.3e-6)[0].channel[0] == 0
    assert not np.any(at(table, 15.3e-6)[0].injury)
    constant = parse_spec(previous.assembly_definition())
    assert not isinstance(controls.prepare(constant.ionic), controls.ScheduledControl)
    assert controls.storage_bytes(constant.ionic) == 0
    assert clock_identity(True, constant) == clock_identity(True)
    assert clock_identity(True, spec) != clock_identity(True, constant)


def test_schedule_splits_enter_working_and_step_budgets():
    raw = fixtures.assembly_definition()
    spec = parse_spec(raw)
    constant = deepcopy(raw)
    for row in constant["ionic"]["experiment"]["injury_controls"]:
        row["schedule"] = row["schedule"][:1]
    fixed = parse_spec(constant)
    assert spec.working_bytes - fixed.working_bytes == controls.storage_bytes(spec.ionic)
    assert spec.output_bound > fixed.output_bound
    raw["ionic"]["execution"]["max_steps"] = spec.ticks
    with pytest.raises(AssemblyError, match="budget"):
        parse_spec(raw)
    raw["ionic"]["execution"]["max_steps"] += 2
    assert parse_spec(raw).ticks == spec.ticks


def test_initial_owned_readouts_and_ensemble_aggregation():
    raw = fixtures.assembly_definition()
    raw["ionic"]["model"]["injury_patches"][0]["initial_damage"] = 0.25
    spec = parse_spec(raw)
    state = engine.initial_state(spec)
    row = engine.summary(spec, state) | dict(
        execute_seconds=0.0, arm="repair", wall_start=0.0, wall_end=1.0
    )
    assert set(("calcium", "calcium_channels", "ip3", "injury")) <= set(row)
    assert row["physical_model"] == "resolved_repair@1"
    assert row["injury"]["patch_ids"] == row["voltage_owner_ids"]
    for name in model.EXTRA_AXES:
        np.testing.assert_array_equal(row["injury"][name], getattr(state.ionic, name)[..., :4])
    total = aggregate([row, row])["repair"]
    assert total["worlds"] == 2 * spec.pool.worlds
    for name in model.EXTRA_AXES:
        np.testing.assert_array_equal(
            total["injury"][name + "_sum_over_worlds"],
            2 * np.asarray(row["injury"][name]).sum(axis=0),
        )
    for fault in ("missing", "axes", "patch", "owner", "species", "damage", "transfer", "nan"):
        wrong = deepcopy(row)
        data = wrong["injury"]
        if fault == "missing":
            wrong.pop("injury")
        elif fault == "axes":
            data["transfer_axes"] = ["world", "membrane_patch", "species"]
        elif fault == "patch":
            data["patch_ids"].reverse()
        elif fault == "owner":
            data["cell_ids"][0] = "missing"
        elif fault == "species":
            data["species_ids"].reverse()
        elif fault == "damage":
            data["damage"][0][0] = 1.1
        elif fault == "transfer":
            data["injury_transferred"] = data["injury_transferred"][:-1]
        else:
            data["injury_dissipated_energy_pJ"][0][0][0] = float("nan")
        with pytest.raises(ValueError, match="injury"):
            aggregate([wrong])
    evidence("assembly-repair-readouts", dict(status="passed", inputs=spec.to_dict(), report=row))


def test_injury_and_assembly_rates_have_independent_owners():
    raw = fixtures.assembly_definition()
    raw["ionic"]["model"]["injury_patches"][0]["initial_damage"] = 0.2
    spec = parse_spec(raw)
    state, p = model.initial_values(spec.ionic)
    table = control_values(spec.ionic, [5.3e-6])
    held = type(table)(*(v[0] for v in table))
    opening = np.array([0.2, 0.8])
    held = held._replace(channel=held.channel * opening[channel_owners(spec)])
    actual = model.readouts(state, held, p, xp=np)
    c = reference.bind(spec.ionic.to_dict())
    expected, _, proof = reference.evaluate(c, reference.initial(c), 5.3e-6, channel_levels=opening)
    ratio = assert_states(
        c,
        reference.flatten(c, actual.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    stopped = model.readouts(state, held._replace(channel=np.zeros_like(held.channel)), p, xp=np)
    np.testing.assert_array_equal(
        stopped.derivative.injury_transferred, actual.derivative.injury_transferred
    )
    np.testing.assert_array_equal(stopped.derivative.damage, actual.derivative.damage)
    assert np.any(actual.derivative.injury_transferred != 0)
    assert abs(proof["physical_energy_balance_pJ_s"]) < 1e-10
    evidence(
        "assembly-repair-rates",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            max_error_over_budget=ratio,
            scope="Independent numerical rate/ownership control; no biological repair claim",
        ),
    )


def test_complete_initial_checkpoint_clock_identity_and_segment_guards(tmp_path):
    spec = parse_spec(fixtures.assembly_definition())
    state = engine.initial_state(spec)
    path = tmp_path / "initial"
    write_checkpoint(path, spec, state, backend="cpu")
    restored_spec, restored, _ = load_checkpoint(path, backend="cpu")
    same(state, restored)
    assert restored_spec.fingerprint == spec.fingerprint
    manifest = json.loads((path / "manifest.json").read_text())
    assert "control_events" in manifest["clock"]
    manifest["clock"] = clock_identity(True)
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(AssemblyError, match="clock"):
        load_checkpoint(path, backend="cpu")
    # At tick 16 the off-grid opening boundary has added exactly one segment.
    state.tick[:] = 16
    state.pool.time_s[:] = 16 * spec.ionic.execution.dt
    state.segments[:] = 17
    engine.validate_state(spec, state)
    for count in (16, 18):
        state.segments[:] = count
        with pytest.raises(AssemblyError, match="integration"):
            engine.validate_state(spec, state)
    state.segments[:] = 17
    state.ionic.damage[0, 0] = 1.1
    with pytest.raises(NumericalError, match="injury"):
        engine.validate_state(spec, state)


def test_one_to_sixteen_gpu_planning_preserves_injury_schedules_and_worlds():
    raw = ensemble_definition()
    definition = fixtures.assembly_definition(backend="gpu")
    for binding in definition["pools"]:
        for name in ("worlds", "world_id_start", "seed"):
            binding["pool"].pop(name)
    raw["arms"][0]["definition"] = definition
    local, future = plan(raw, 1), jupiter_plan(raw, 4)
    assert local["tasks"] == future["tasks"]
    assert future["deployment"]["maximum_target_gpus"] == 16
    assert not future["deployment"]["remote_execution_qualified"]
    identities = []
    for task in future["tasks"]:
        spec = parse_spec(task["definition"])
        assert spec.ionic.to_dict()["model"]["id"] == "resolved_repair@1"
        assert controls.extra_boundaries(spec.ionic) == 2
        identities.extend(
            range(spec.pool.world_id_start, spec.pool.world_id_start + spec.pool.worlds)
        )
    assert sorted(identities) == list(range(64))
    evidence(
        "assembly-repair-planning",
        dict(
            status="passed",
            world_ids=sorted(identities),
            maximum_target_gpus=16,
            gpu_execution=False,
            remote_execution_qualified=False,
        ),
    )


@pytest.fixture(scope="module")
def coupled():
    spec = parse_spec(fixtures.assembly_definition(backend=BACKEND))
    requested = {
        round(t / spec.ionic.execution.dt) for t in spec.ionic.experiment.observation_times
    }
    samples = [flatten(engine.initial_state(spec))]

    def capture(_, current):
        if int(current.tick[0]) in requested:
            samples.append({k: v.copy() for k, v in flatten(current).items()})

    state, report = engine.run(spec, backend=BACKEND, callback=capture)
    observed = {k: np.stack([row[k] for row in samples]) for k in samples[0]}
    evidence(
        "assembly-repair-compiled",
        dict(status="captured", report=report, inputs=spec.to_dict()),
        flatten(state),
    )
    evidence(
        "assembly-repair-observations", dict(status="captured", inputs=spec.to_dict()), observed
    )
    np.testing.assert_array_equal(observed["tick"][:, 0], sorted(requested))
    return spec, state, report, observed


def test_compiled_joint_trajectory_matches_independent_event_reference(coupled):
    spec, state, report, observed = coupled
    events = event_histories(spec, state, 0)
    times = sorted({0.0, *(e[0] for rows in events.values() for e in rows)})
    segments = []
    for time in times:
        levels = []
        for binding in spec.pools:
            past = [e for e in events[binding.cell_id] if e[0] <= time]
            mask, bonds = (
                past[-1][1:3] if past else (binding.pool.initial_mask, binding.pool.initial_bonds)
            )
            levels.append(
                binding.active_availability
                if bonds.bit_count() >= mask.bit_count()
                else binding.inactive_availability
            )
        segments.append((time, levels))
    assert len(segments) > 1 and len({tuple(v) for _, v in segments}) > 1
    raw = spec.ionic.to_dict()
    expected = reference.integrate(raw, channel_segments=segments)
    c = reference.bind(raw)
    actual = reference.flatten(c, {k: observed["ionic_" + k][:, 0] for k in state.ionic._fields})
    evidence(
        "assembly-repair-reference-inputs",
        dict(
            inputs=raw,
            channel_segments=segments,
            reference=expected["method"],
            rtol=expected["rtol"],
            atol=expected["atol"],
        ),
        dict(actual=actual, reference=expected["state"]),
    )
    ratio = assert_states(c, actual, expected["state"])
    assert np.all(state.ionic.damage[:, 0] > 0)
    assert np.all(state.ionic.damage_closed[:, 0] > 0)
    assert report["ionic_accounting"]["max_damage_ledger_error"] < 2**-40
    evidence(
        "assembly-repair-reference",
        dict(
            status="passed",
            max_error_over_budget=ratio,
            assembly_events={k: len(v) for k, v in events.items()},
            observation_times_s=raw["experiment"]["observation_times"],
            scope="50-us synthetic numerical control",
        ),
    )


def test_compiled_complete_restart_windows_and_world_partition(coupled, tmp_path):
    spec, whole, _, _ = coupled
    half, _ = engine.run(spec, backend=BACKEND, until=20e-6)
    write_checkpoint(tmp_path / "repair", spec, half, backend=BACKEND)
    saved, checkpoint, _ = load_checkpoint(tmp_path / "repair", backend=BACKEND)
    same(half, checkpoint)
    resumed, _ = engine.run(replace(saved, window_ticks=3), backend=BACKEND, state=checkpoint)
    evidence("assembly-repair-resumed", dict(inputs=saved.to_dict()), flatten(resumed))
    same(whole, resumed)
    parts = []
    for start in range(spec.pool.worlds):
        raw = bind_definition(spec.to_dict(), worlds=1, world_id_start=start, seed=spec.pool.seed)
        part, _ = engine.run(parse_spec(raw), backend=BACKEND)
        evidence(f"assembly-repair-world-{start}", dict(inputs=raw), flatten(part))
        parts.append(part)
    merged = jax.tree.map(lambda *values: np.concatenate(values), *parts)
    same(whole, merged)
    evidence(
        "assembly-repair-replay",
        dict(
            status="passed",
            saved_restart_bitwise=True,
            changed_windows_bitwise=True,
            partitioned_worlds_bitwise=True,
            world_ids=list(range(spec.pool.worlds)),
        ),
    )


def test_cpu_gpu_complete_assembly_state_and_observations(coupled):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU assembly states")
    assert EVIDENCE
    spec, state, _, observed = coupled
    raw = spec.to_dict()
    raw["ionic"] = normalized(raw["ionic"])
    directory = Path(EVIDENCE) / "cpu"
    for name in ("assembly-repair-reference", "assembly-repair-replay"):
        assert json.loads((directory / (name + ".json")).read_text())["status"] == "passed"
    count = 0
    for name, actual in (
        ("assembly-repair-compiled", flatten(state)),
        ("assembly-repair-observations", observed),
    ):
        assert json.loads((directory / (name + ".json")).read_text())["inputs"] == raw
        with np.load(directory / (name + ".npz"), allow_pickle=False) as saved:
            count += compare_backend(actual, saved)
    evidence(
        "assembly-repair-cpu-gpu",
        dict(
            status="passed",
            scalar_values=count,
            exact_discrete_events=True,
            rtol=3e-10,
            state_atol=3e-13,
            charge_atol_C=3e-25,
        ),
    )
