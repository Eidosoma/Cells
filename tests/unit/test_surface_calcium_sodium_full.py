"""Complete sodium/calcium execution qualification using existing physical checks.

The initial wiring suite remains separately runnable. This module adds full
trajectories, both baseline/release refinements, replay, heterogeneous worlds and
assembly dynamics. Collection or host planning is not a passing qualification.
"""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from cells.assembly_cluster.spec import channel_owners
from cells.core.batch import BatchSpec, WorldSpec, plan_batch, run_batch
from cells.core.resources import trace_bytes
from cells.core.runner import branch_checkpoint, run, timeline
from cells.core.specs import ConfigError, parse_spec
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_calcium_sodium as model
from tests.unit import test_surface_calcium as shared
from tests.unit import test_surface_calcium_sodium as wiring
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import surface_calcium_reference as reference
from validation.tissue import surface_calcium_sodium_fixtures as fixtures

BACKEND, EVIDENCE, PREFIX = wiring.BACKEND, wiring.EVIDENCE, wiring.PREFIX
REFINEMENT_STEPS = (2.5e-6, 1.25e-6, 0.625e-6)
BATCH_STEP_BUDGET = 2048
SINGLE_WORLD_STEP_BUDGET = 1024
BATCH_WORKING_BYTES = 2**31


@pytest.fixture(scope="module", autouse=True)
def composition_context():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(shared, "model", model)
        patch.setattr(shared, "fixtures", fixtures)
        patch.setattr(shared, "PREFIX", PREFIX)
        patch.setattr(shared, "REFINEMENT_STEPS", REFINEMENT_STEPS)
        patch.setattr(shared, "BATCH_STEP_BUDGET", BATCH_STEP_BUDGET)
        patch.setattr(shared, "SINGLE_WORLD_STEP_BUDGET", SINGLE_WORLD_STEP_BUDGET)
        patch.setattr(shared, "BATCH_WORKING_BYTES", BATCH_WORKING_BYTES)
        patch.setattr(shared, "REPLAY_WINDOW_STEPS", 17)
        yield


def evidence(name, value):
    shared.evidence(PREFIX + "-" + name, value)


def heterogeneous_definition(*, backend="cpu"):
    raw = fixtures.definition(backend=backend)
    # Same model/array layout, different law AND transported species in one
    # population. The other sodium population and chemical ownership stay live.
    raw["model"]["ionic"]["channels"][5].update(species_id="K", kinetic_law="betse_kv1p5_mh@1")
    return raw


def test_execution_grids_and_work_budgets():
    grids = []
    for arm in fixtures.ARMS:
        for dt in REFINEMENT_STEPS:
            raw = fixtures.definition(arm)
            raw["execution"]["dt"] = dt
            spec = parse_spec(raw)
            grid = timeline(spec)
            assert all(t in grid for t in spec.experiment.observation_times)
            grids.append(
                dict(
                    arm=arm,
                    dt_s=dt,
                    accepted_steps=len(grid) - 1,
                    max_steps=spec.execution.max_steps,
                    estimated_trace_bytes=trace_bytes(spec, len(grid) - 1),
                    max_trace_bytes=spec.execution.max_trace_bytes,
                )
            )
    default = [parse_spec(fixtures.definition(arm)) for arm in ("baseline", "release")]
    plans = []
    for name, specs in (
        ("independent_clocks", default),
        ("heterogeneous_laws", [default[0], parse_spec(heterogeneous_definition())]),
    ):
        batch = BatchSpec(
            tuple(WorldSpec(23 + 18 * i, s) for i, s in enumerate(specs)),
            2,
            BATCH_STEP_BUDGET,
            BATCH_WORKING_BYTES,
        )
        planned = plan_batch(batch)
        # The old coarse-calcium cap cannot accommodate this finer grid.
        with pytest.raises(ConfigError, match="padded work"):
            plan_batch(BatchSpec(batch.worlds, 2, 200, BATCH_WORKING_BYTES))
        for world in batch.worlds:
            plan_batch(BatchSpec((world,), 1, SINGLE_WORLD_STEP_BUDGET, BATCH_WORKING_BYTES))
        plans.append(
            dict(
                name=name,
                conservative_padded_steps=planned.padded_step_bound,
                budget=BATCH_STEP_BUDGET,
                estimated_working_bytes=planned.estimated_working_bytes,
                max_working_bytes=BATCH_WORKING_BYTES,
            )
        )
    spec = shared.parse_assembly(fixtures.assembly_definition())
    assert spec.ticks == 800
    assert spec.ionic.execution.dt == REFINEMENT_STEPS[0]
    evidence(
        "execution-plan",
        dict(
            status="passed",
            grids=grids,
            batches=plans,
            assembly_ticks=spec.ticks,
            scope="Host planning only; no trajectories or GPU execution",
        ),
    )


def test_heterogeneous_population_independent_rates():
    spec, state, p, control = wiring.initial(heterogeneous_definition())
    actual = model.readouts(state, control, p, xp=np)
    c = reference.bind(spec.to_dict())
    expected, _, proof = reference.evaluate(c, reference.initial(c), 0.0)
    ratio = assert_states(
        c,
        reference.flatten(c, actual.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    assert spec.model.channels[5].species_id == "K"
    assert spec.model.channels[6].species_id == "Na"
    evidence(
        "heterogeneous-stage",
        dict(
            status="passed",
            inputs=spec.to_dict(),
            max_error_over_budget=ratio,
            independent_root=proof,
            scope="Numerical world-routing control",
        ),
    )


def test_assembly_controls_each_cells_sodium_and_potassium():
    spec = shared.parse_assembly(fixtures.assembly_definition())
    _, state, p, control = wiring.initial(spec.ionic.to_dict())
    owners = channel_owners(spec)
    np.testing.assert_array_equal(owners, [0, 0, 1, 1, 0, 0, 1, 0])
    levels = np.array([0.0, 1.0])
    held = control._replace(channel=control.channel * levels[owners])
    before, after = (model.readouts(state, c, p, xp=np) for c in (control, held))
    assert before.derivative.channel_transferred[5] != 0
    assert not np.any(after.derivative.channel_transferred[[0, 1, 4, 5]])
    np.testing.assert_array_equal(
        after.derivative.channel_transferred[[2, 3, 6]],
        before.derivative.channel_transferred[[2, 3, 6]],
    )
    exact((after.derivative.channel_gate,), (before.derivative.channel_gate,))
    c = reference.bind(spec.ionic.to_dict())
    expected, _, proof = reference.evaluate(c, reference.initial(c), 0.0, channel_levels=levels)
    ratio = assert_states(
        c,
        reference.flatten(c, after.derivative._asdict()),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    evidence(
        "assembly-owner-control",
        dict(
            status="passed",
            channel_owner_indices=owners.tolist(),
            cell_levels=levels.tolist(),
            max_error_over_budget=ratio,
            independent_root=proof,
            intrinsic_gates_unchanged=True,
            scope="Initial rates; assembly dynamics checked separately",
        ),
    )


@pytest.mark.parametrize("family", ["store", "plasma", "calcium_channel"])
def test_chemical_only_event_trajectory_and_restart(family, tmp_path):
    event_time = 37e-6  # Between the 35-us and 37.5-us nominal sodium steps.
    raw = fixtures.definition(backend=BACKEND)
    raw["experiment"].update(end_time=50e-6, observation_times=[0.0, 25e-6, event_time, 50e-6])
    key = "controls" if family == "store" else "schedule"
    changes = raw["experiment"][family + "_controls"][0][key]
    changed = deepcopy(changes[0]) | {"time": event_time}
    if family == "store":
        changed["release"] = 0.0
        ledgers = ("er_release_transferred",)
    elif family == "plasma":
        changed.update(pump=0.0, exchanger=0.0)
        ledgers = ("plasma_pump_cycles", "plasma_exchange_cycles")
    else:
        changed["availability"] = 0.0
        ledgers = ("calcium_channel_transferred",)
    changes.append(changed)
    value = run(parse_spec(raw))
    assert all(v.device.platform == BACKEND for v in value.final.state)
    checkpoint = value.checkpoint_at(event_time)
    index = checkpoint.step_index
    assert value.times[index - 1] < event_time < value.times[index + 1]
    for name in ledgers:
        history = np.asarray(getattr(value.history, name))
        assert np.any(history[index, 0] != history[0, 0])
        np.testing.assert_array_equal(
            history[index:, 0], np.broadcast_to(history[index, 0], history[index:, 0].shape)
        )
        # The other owner/patch continues; the intervention is local.
        assert np.any(history[-1, 1] != history[index, 1])
    if family == "calcium_channel":
        assert np.any(
            value.history.calcium_gate[-1, :, 0] != value.history.calcium_gate[index, :, 0]
        )
    c = reference.bind(value.spec.to_dict())
    expected = reference.integrate(value.spec.to_dict())
    ratio = assert_states(
        c, reference.flatten(c, vars(value.observations)), np.asarray(expected["state"])
    )
    write_snapshot(tmp_path / "chemical-event", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "chemical-event")
    exact(loaded.checkpoint.state, checkpoint.state)
    assert loaded.spec == value.spec
    resumed = run(loaded.spec, loaded.checkpoint)
    exact(resumed.history, tuple(v[index:] for v in value.history))
    evidence(
        "chemical-event-" + family,
        dict(
            status="passed",
            inputs=value.spec.to_dict(),
            event_time_s=event_time,
            stopped_ledgers=list(ledgers),
            complete_disk_restart="bitwise",
            max_state_error_over_budget=ratio,
            independent_reference=expected,
            diagnostics=value.diagnostics,
            run_timings=value.timings,
            resume_timings=resumed.timings,
            scope="50-us event-clock/replay control, not an independent biological case",
        ),
    )


# Preserve the older family's defaults and assertions through a scoped adapter.
trajectories = shared.trajectories
coupled = shared.coupled
test_registered_roundtrip_and_ensemble = shared.test_registered_roundtrip_and_ensemble
test_internal_chemistry_uses_free_ions_without_charging_plasma = (
    shared.test_internal_chemistry_uses_free_ions_without_charging_plasma
)
test_corrupt_complete_ledgers_or_inventories_are_rejected = (
    shared.test_corrupt_complete_ledgers_or_inventories_are_rejected
)
test_inconsistent_definitions_reject = shared.test_inconsistent_definitions_reject
test_failed_field_and_actual_controls_reject = shared.test_failed_field_and_actual_controls_reject
test_chemical_event_is_an_accepted_observation_boundary = (
    shared.test_chemical_event_is_an_accepted_observation_boundary
)
test_existing_resolved_kinetics_preserve_rates_and_energy = (
    shared.test_existing_resolved_kinetics_preserve_rates_and_energy
)
test_evolved_stage_preserves_owned_charge_and_independent_rates = (
    shared.test_evolved_stage_preserves_owned_charge_and_independent_rates
)
test_new_model_rejects_held_bath_with_explicit_scope = (
    shared.test_new_model_rejects_held_bath_with_explicit_scope
)
test_absent_routes_and_zero_reaction_capacity_keep_zero_ledgers = (
    shared.test_absent_routes_and_zero_reaction_capacity_keep_zero_ledgers
)
test_independent_trajectories_and_complete_accounting = (
    shared.test_independent_trajectories_and_complete_accounting
)
test_timestep_refinement = shared.test_timestep_refinement
test_compiled_guard_rejects_actual_invalid_control_without_changing_state = (
    shared.test_compiled_guard_rejects_actual_invalid_control_without_changing_state
)
test_complete_disk_fresh_process_restart_branch_and_windows = (
    shared.test_complete_disk_fresh_process_restart_branch_and_windows
)
test_world_partition_reorder_and_independent_restart = (
    shared.test_world_partition_reorder_and_independent_restart
)
test_ensemble_endpoint_reports_real_patch_voltages_and_complete_state = (
    shared.test_ensemble_endpoint_reports_real_patch_voltages_and_complete_state
)
test_cpu_gpu_complete_saved_states_and_observations = (
    shared.test_cpu_gpu_complete_saved_states_and_observations
)
test_assembly_event_reference = shared.test_assembly_event_reference
test_assembly_restart_partition_and_ligand_response = (
    shared.test_assembly_restart_partition_and_ligand_response
)
test_sixteen_gpu_planning_keeps_worlds_and_model = (
    shared.test_sixteen_gpu_planning_keeps_worlds_and_model
)
test_assembly_aggregation_retains_owned_ligand = (
    shared.test_assembly_aggregation_retains_owned_ligand
)


@pytest.fixture(scope="module")
def references(composition_context):
    if BACKEND == "gpu" and EVIDENCE:
        result = {}
        for arm in fixtures.ARMS:
            saved = json.loads(
                (Path(EVIDENCE) / "cpu" / (PREFIX + "-trajectory-" + arm + ".json")).read_text()
            )
            assert saved["status"] == "passed"
            assert saved["inputs"] == parse_spec(fixtures.definition(arm)).to_dict()
            result[arm] = saved["independent_reference"]
        return result
    return {arm: reference.integrate(fixtures.definition(arm)) for arm in fixtures.ARMS}


def test_release_refinement(trajectories, references):
    shared.refinement_case(trajectories, references, "release")


@pytest.mark.parametrize("change", ["law", "species_and_law"])
def test_restart_rejects_changed_population(trajectories, change):
    value = trajectories["baseline"]
    raw = value.spec.to_dict()
    if change == "law":
        raw["model"]["ionic"]["channels"][1]["kinetic_law"] = "betse_kv1p5_mh@1"
    else:
        raw["model"]["ionic"]["channels"][5].update(species_id="K", kinetic_law="betse_kv1p5_mh@1")
    valid_alternative = parse_spec(raw)
    with pytest.raises(ConfigError, match="model or execution"):
        branch_checkpoint(value.spec, value.checkpoint_at(0.001), valid_alternative)
    evidence("identity-" + change, dict(status="passed", changed_population_branch_rejected=True))


def test_channel_species_and_laws_remain_owned_by_each_world(trajectories):
    baseline = trajectories["baseline"]
    alternate = run(parse_spec(heterogeneous_definition(backend=BACKEND)))
    assert np.any(alternate.history.channel_gate != baseline.history.channel_gate)
    assert np.any(
        alternate.history.chemical_amount_increment != baseline.history.chemical_amount_increment
    )
    spec = BatchSpec(
        (WorldSpec(23, baseline.spec), WorldSpec(41, alternate.spec)),
        2,
        BATCH_STEP_BUDGET,
        BATCH_WORKING_BYTES,
    )
    batch = run_batch(spec)
    exact(batch.worlds[23].history, baseline.history)
    exact(batch.worlds[41].history, alternate.history)
    evidence(
        "world-laws",
        dict(
            status="passed",
            comparison="bitwise against each standalone world",
            world_ids=[23, 41],
            populations=[
                [(ch.species_id, ch.kinetic_law) for ch in v.spec.model.channels]
                for v in (baseline, alternate)
            ],
            scope="Numerical species/law-routing control, not an independent biological case",
        ),
    )
