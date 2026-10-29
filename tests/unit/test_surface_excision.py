"""Physical survivors, explicit cut energy, absolute clocks and full restart."""

import json
from dataclasses import replace
from functools import lru_cache

import numpy as np
import pytest

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.runner import run, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint, initialise
from cells.core.surface_excision_spec import MODEL_ID, base_spec
from cells.core.tissue_excision import capture_source, decode_source, excise
from cells.core.windows import WindowPolicy, iter_windows, plan_windows, run_windowed
from cells.excision_io import load_excision, write_excision
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_excision as model
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_tissue import assert_states, exact
from validation.tissue import surface_excision_fixtures as fixtures
from validation.tissue import surface_excision_reference as reference

TRAJECTORY_REFINEMENT = 256


def trajectory_definition(arm="open", padded=True):
    raw = fixtures.definition(arm, padded=padded)
    raw["execution"].update(
        dt=fixtures.DT / TRAJECTORY_REFINEMENT, max_steps=100000, max_trace_bytes=8 * 2**30
    )
    return raw


@lru_cache(maxsize=16)
def source_reference(arm):
    return reference.integrate(fixtures.definition(arm), end_time=fixtures.CUT_TIME)


@lru_cache(maxsize=16)
def prepared(arm="open", padded=True):
    raw = fixtures.definition(arm, padded=padded)
    spec = parse_spec(raw)
    context = reference.bind(raw)
    before = source_reference(arm)
    implementation = get_model(spec.model)
    state, layout = implementation.initial_values(spec)
    for key, value in reference.unpack(context, before["state"][-1]).items():
        getattr(state, key)[tuple(slice(0, n) for n in value.shape)] = value
    time = fixtures.CUT_TIME
    point = Checkpoint(
        state, layout, time, EventGrid(spec).exact_index(time), event_index(spec, time)
    )
    implementation.check_values(state, spec)
    return spec, point


def compare_transition(spec, point, cut):
    before = reference.bind(spec.to_dict())
    expected = reference.excise(
        spec.to_dict(),
        reference.flatten(before, point.state._asdict()),
        cut.report["removed_cell_ids"],
        point.time,
    )
    if cut.spec is None:
        assert expected["raw"] is None
        return expected
    ordinary = (
        base_spec(cut.spec).to_dict()
        if cut.spec.model.__class__ is not spec.model.__class__ or cut.report["changed"]
        else cut.spec.to_dict()
    )
    if cut.report["changed"]:
        np.testing.assert_allclose(
            np.asarray(cut.report["removed_amount_fmol"]).sum(axis=-1),
            expected["audit"]["removed_amount_fmol"],
            atol=2e-11,
            rtol=3e-12,
        )
    c = reference.bind(ordinary)
    y = reference.flatten(c, cut.checkpoint.state._asdict())
    table = control_values(cut.spec, [point.time])
    u = type(table)(*(v[0] for v in table))
    impl = get_model(cut.spec.model)
    got = impl.rhs(
        cut.checkpoint.state, u, cut.checkpoint.layout, cut.checkpoint.layout.active, xp=np
    )
    target, _, _ = reference.evaluate(c, y, point.time)
    ratio = assert_states(
        c, reference.flatten(c, got._asdict()), target, atol=3e-12, charge_atol=3e-23, rtol=3e-10
    )
    if cut.report["changed"]:
        for key, reference_key in (
            ("unresolved_cut_energy_pJ", "unresolved_cut_energy_pJ"),
            ("held_boundary_work_impulse_pJ", "maintained_boundary_work_pJ"),
        ):
            np.testing.assert_allclose(
                cut.report[key], expected["audit"][reference_key], atol=2e-10, rtol=3e-9
            )
        np.testing.assert_allclose(
            cut.report["electrode_charge_impulse_C"],
            expected["audit"]["electrode_charge_impulse_C"],
            atol=3e-25,
            rtol=3e-10,
        )
    return dict(
        max_error_over_budget=ratio,
        transition=json.loads(json.dumps(expected["audit"], default=lambda v: v.tolist())),
    )


@pytest.mark.parametrize("arm", ["open", "clamped", "blocked", "no-op", "single-survivor"])
@pytest.mark.parametrize("padded", [False, True])
def test_nonzero_source_cut_matches_independent_material_fields_and_rates(arm, padded):
    spec, point = prepared(arm, padded)
    state = tuple(np.array(v) for v in point.state)
    cut = excise(spec, point, fixtures.cut_plan(arm)[0]["removed_cell_ids"])
    checked = compare_transition(spec, point, cut)
    exact(state, point.state)
    assert cut.checkpoint.time == point.time
    assert cut.spec == parse_spec(cut.spec.to_dict())
    assert all(abs(v) <= 2e-11 for v in cut.report["material_residual_fmol"])
    if arm == "no-op":
        assert cut.spec == spec and cut.checkpoint is point
        exact(cut.checkpoint.state, point.state)
    else:
        assert get_model(cut.spec.model) is model
        assert len(cut.checkpoint.state) == 12 and all(not np.any(v) for v in cut.checkpoint.state)
        restored_spec, restored = decode_source(capture_source(spec, point))
        assert restored_spec == spec
        exact(restored.state, point.state)
        exact(restored.layout, point.layout)
        assert np.max(np.abs(point.state.membrane_transferred)) > 0 or arm == "blocked"
    evidence(
        f"excision-stage-{arm}-{padded}",
        dict(status="passed", source=spec.to_dict(), report=cut.report, comparison=checked),
    )


@pytest.mark.parametrize("arm", ["closed", "disconnected"])
def test_unsolvable_cuts_leave_source_untouched(arm):
    spec, point = prepared(arm)
    before = tuple(np.array(v) for v in (*point.state, *point.layout))
    with pytest.raises(ConfigError) as error:
        excise(spec, point, fixtures.cut_plan(arm)[0]["removed_cell_ids"])
    exact(before, (*point.state, *point.layout))
    evidence(
        "excision-rejected-" + arm,
        dict(
            status="expected_rejection",
            source=capture_source(spec, point),
            attempted_removal=fixtures.cut_plan(arm)[0],
            failure=str(error.value),
            source_unchanged=True,
        ),
    )


def test_absolute_time_initialization_retains_removed_only_events():
    spec, point = prepared()
    cut = excise(spec, point, ["cell_1"])
    assert cut.spec.to_dict()["model"]["id"] == MODEL_ID
    created = initialise(cut.spec)
    assert created.time == point.time and created.step_index == point.step_index
    exact(created.state, cut.checkpoint.state)
    assert set(timeline(spec)) == set(timeline(cut.spec))
    assert 0.001237 in [v.time for v in cut.spec.experiment.changes]
    assert min(cut.spec.experiment.observation_times) == point.time
    with pytest.raises(ConfigError, match="epoch"):
        validate_checkpoint(cut.spec, replace(created, time=0.0, step_index=0, event_index=0))
    wrong = created.state._replace(
        amount_increment=np.asarray(created.state.amount_increment).copy()
    )
    wrong.amount_increment[0, 0] += 1e-18
    with pytest.raises(ConfigError, match="initial state"):
        validate_checkpoint(cut.spec, replace(created, state=wrong))


@pytest.mark.parametrize(
    "fault", ["time", "event", "shape", "state", "layout", "unknown", "duplicate"]
)
def test_invalid_source_or_removal_is_rejected(fault):
    spec, point = prepared()
    ids = ["cell_1"]
    if fault == "time":
        point = replace(point, time=point.time + 1e-9)
    elif fault == "event":
        point = replace(point, event_index=point.event_index + 1)
    elif fault == "shape":
        point = replace(point, state=point.state._replace(amount_increment=np.zeros((1, 1))))
    elif fault == "state":
        point = replace(
            point,
            state=point.state._replace(
                amount_increment=np.full_like(point.state.amount_increment, np.nan)
            ),
        )
    elif fault == "layout":
        point = replace(point, layout=point.layout._replace(volume=point.layout.volume * 2))
    elif fault == "unknown":
        ids = ["absent"]
    else:
        ids *= 2
    with pytest.raises((ConfigError, NumericalError)):
        excise(spec, point, ids)


@pytest.mark.parametrize(
    "fault",
    [
        "policy",
        "inventory",
        "charge",
        "volume",
        "past",
        "source_layout",
        "layout_type",
        "state_type",
        "dt",
        "past_control",
        "lost_clock",
    ],
)
def test_serialized_cut_cannot_hide_changed_owners_or_history(fault):
    spec, point = prepared()
    raw = excise(spec, point, ["cell_1"]).spec.to_dict()
    m = raw["model"]
    if fault == "policy":
        m["excision"]["state_policy"] = "discard_history"
    elif fault == "inventory":
        m["tissue"]["cells"][0]["initial_amount_fmol"]["Na"] += 0.1
    elif fault == "charge":
        m["tissue"]["cells"][0]["initial_charge_C"] += 1e-15
    elif fault == "volume":
        m["tissue"]["cells"][0]["volume_pL"] *= 2
    elif fault == "past":
        raw["experiment"]["observation_times"].insert(0, 0.0)
    elif fault == "source_layout":
        m["excision"]["source"]["checkpoint"]["layout"]["volume"][0] *= 2
    elif fault == "layout_type":
        m["excision"]["source"]["checkpoint"]["layout"]["active"][0] = 1
    elif fault == "state_type":
        m["excision"]["source"]["checkpoint"]["state"]["amount_increment"][0][0] = "0"
    elif fault == "dt":
        raw["execution"]["dt"] /= 2
    elif fault == "past_control":
        raw["experiment"]["membrane_controls"][0]["schedule"][0]["availability"] = 0.0
    else:
        for row in raw["experiment"]["membrane_controls"]:
            row["schedule"] = [v for v in row["schedule"] if v["time"] != 0.001237]
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize("selection", [["cell_1"], [], ["cell_0", "cell_1", "cell_2"]])
def test_complete_excision_artifact_roundtrip_and_checksum(tmp_path, selection):
    spec, point = prepared()
    cut = excise(spec, point, selection)
    target = write_excision(tmp_path / "cut", cut)
    loaded = load_excision(target)
    assert loaded.spec == cut.spec and loaded.report == cut.report
    exact(loaded.source_checkpoint.state, point.state)
    exact(loaded.source_checkpoint.layout, point.layout)
    if cut.checkpoint is not None:
        exact(loaded.checkpoint.state, cut.checkpoint.state)
        exact(loaded.checkpoint.layout, cut.checkpoint.layout)
    else:
        assert loaded.report["terminal"]
    with pytest.raises(FileExistsError):
        write_excision(target, cut)
    (target / "transition.json").write_text("{}\n")
    with pytest.raises(ConfigError, match="checksum"):
        load_excision(target)


def test_sequential_same_time_cuts_preserve_absolute_owners_and_history():
    spec, point = prepared()
    first = excise(spec, point, ["cell_1"])
    second = excise(first.spec, first.checkpoint, ["cell_0"])
    combined = excise(spec, point, ["cell_0", "cell_1"])
    assert base_spec(second.spec).model == base_spec(combined.spec).model
    assert second.checkpoint.time == point.time
    np.testing.assert_allclose(
        second.report["postcut_voltage_V"],
        combined.report["postcut_voltage_V"],
        atol=3e-14,
        rtol=3e-12,
    )
    previous = json.loads(second.spec.model.excision_json)["source"]["definition"]
    assert (
        previous["model"]["excision"]["source"]["checkpoint"]["state"]
        == capture_source(spec, point)["checkpoint"]["state"]
    )


def test_cli_writes_reusable_cut_snapshot(tmp_path, capsys):
    from cells.__main__ import main

    spec, point = prepared()
    write_snapshot(tmp_path / "source", spec, point)
    assert (
        main(
            [
                "excise",
                str(tmp_path / "source"),
                "--remove",
                "cell_1",
                "--output",
                str(tmp_path / "cut"),
            ]
        )
        == 0
    )
    status = json.loads(capsys.readouterr().out)
    assert status["status"] == "complete" and not status["terminal"]
    loaded = load_excision(tmp_path / "cut")
    assert loaded.checkpoint.time == point.time
    assert loaded.report["retained_cell_ids"] == ["cell_0", "cell_2"]


def test_window_and_batch_plans_begin_at_cut_epoch():
    from cells.core.batch_windows import plan_batch_windows

    spec, point = prepared()
    cut = excise(spec, point, ["cell_1"])
    policy = WindowPolicy(64)
    plan = plan_windows(cut.spec, policy)
    assert plan.start_step == point.step_index
    assert plan.grid[plan.start_step] == point.time
    assert plan == plan_windows(cut.spec, policy, cut.checkpoint)
    batch = BatchSpec((WorldSpec(3, cut.spec), WorldSpec(79, cut.spec)), 2, 2048, 2**30)
    paired = plan_batch_windows(batch, policy)
    assert all(v.start_step == point.step_index for v in paired.worlds)


def test_zero_remaining_epoch_supports_scalar_and_batch_windows():
    from cells.core.batch_windows import run_batch_windowed

    spec, point = prepared()
    cut = excise(spec, point, ["cell_1"])
    raw = cut.spec.to_dict()
    raw["experiment"].update(end_time=point.time, observation_times=[point.time])
    for key in ("membrane_controls", "junction_controls"):
        for row in raw["experiment"][key]:
            row["schedule"] = [v for v in row["schedule"] if v["time"] <= point.time]
    finished = parse_spec(raw)
    plan = plan_windows(finished, WindowPolicy(64))
    assert plan.window_count == 1 and plan.start_step == point.step_index
    scalar = run_windowed(finished)
    assert scalar.start_time == scalar.final.time == point.time
    assert scalar.resources["executed_steps"] == 0
    exact(scalar.final.state, cut.checkpoint.state)
    batch = BatchSpec((WorldSpec(3, finished), WorldSpec(79, finished)), 2, 2048, 2**30)
    result = run_batch_windowed(batch)
    for world in result.worlds.values():
        assert world.start_time == world.final.time == point.time
        assert world.resources["executed_steps"] == 0
        exact(world.final.state, cut.checkpoint.state)


def test_offline_sixteen_gpu_plan_preserves_cut_epoch_and_source():
    from cells.ensemble.families import parse_definition, population
    from tests.unit.test_hcn_extra_catalog_planning import verify
    from tests.unit.test_integrated_ensemble import experiment

    spec, point = prepared()
    cut = excise(spec, point, ["cell_1"])
    raw = experiment("ionic", backend="gpu", worlds=16, width=1)
    raw["execution"]["max_output_bytes"] = 4 * 1024**3
    after = cut.spec.to_dict()
    after["execution"]["backend"] = "gpu"
    raw["arms"][0]["definition"]["simulation"] = after
    raw["arms"][0]["definition"]["window_steps"] = 128
    plans = verify(raw)
    identities = []
    for task in plans["local"]["tasks"]:
        definition = parse_definition(task["definition"])
        assert definition.simulation.model.epoch_start_time == point.time
        assert definition.simulation.to_dict()["model"]["excision"] == after["model"]["excision"]
        group = population(definition)
        identities.extend(range(group.world_id_start, group.world_id_start + group.worlds))
    assert sorted(identities) == list(range(16))
    evidence(
        "excision-offline-plans",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            scope="Offline 1/4/16-GPU placement only; no remote execution or utilization claim",
        ),
    )


@pytest.mark.parametrize("phase", ["before", "after"])
def test_host_fast_electrical_transient_refines_without_changing_physics(phase):
    if phase == "before":
        spec = parse_spec(fixtures.definition())
        point = initialise(spec)
    else:
        source, old = prepared(padded=False)
        cut = excise(source, old, ["cell_1"])
        spec, point = cut.spec, cut.checkpoint
    c = reference.bind(spec.to_dict())
    times = [point.time, point.time + fixtures.DT, point.time + 2 * fixtures.DT]
    target = reference.integrate(
        spec.to_dict(), start_time=point.time, end_time=times[-1], observation_times=times
    )
    impl, p = get_model(spec.model), point.layout
    table = control_values(spec, [point.time])
    control = type(table)(*(v[0] for v in table))

    def rhs(y, u, p, active):
        assert impl.control_domain_valid(y, u, p, active, xp=np)
        return impl.rhs(y, u, p, active, xp=np)

    arrays, errors = {}, []
    for refinement in (64, 128, TRAJECTORY_REFINEMENT):
        state = point.state
        saved = [reference.flatten(c, state._asdict())]
        for i in range(2 * refinement):
            state = rk4_step(rhs, state, fixtures.DT / refinement, control, p, p.active)
            if (i + 1) % refinement == 0:
                saved.append(reference.flatten(c, state._asdict()))
        actual = np.stack(saved)
        impl.check_values(state, spec)
        budgets = reference.flatten(
            c, {k: np.full(v, 3e-25 if k.endswith("_C") else 2e-11) for k, v in c["shapes"].items()}
        )
        errors.append(
            float(
                np.max(
                    np.abs(actual - target["state"]) / (budgets + 3e-9 * np.abs(target["state"]))
                )
            )
        )
        arrays[str(refinement)] = actual
    evidence(
        "excision-transient-" + phase,
        dict(
            status="measured",
            input=spec.to_dict(),
            times=times,
            refinements=[64, 128, TRAJECTORY_REFINEMENT],
            max_error_over_budget=errors,
        ),
        dict(reference=target["state"], **arrays),
    )
    assert errors[-1] <= 1
    assert errors[-1] < max(errors[0] / 8, 0.01)


def test_compiled_cut_continuation_and_final_checkpoint(tmp_path):
    raw = trajectory_definition()
    original = parse_spec(raw)
    # Keep the full future schedule while executing only through the actual cut.
    before = next(
        iter_windows(original, WindowPolicy(EventGrid(original).exact_index(fixtures.CUT_TIME)))
    )
    point = before.checkpoint_at(fixtures.CUT_TIME)
    cut = excise(before.spec, point, ["cell_1"])
    result = run(cut.spec)
    assert result.times[0] == point.time and result.start_step == point.step_index
    c = reference.bind(cut.spec.to_dict())
    expected = reference.integrate(cut.spec.to_dict())
    got = reference.flatten(c, vars(result.observations))
    ratio = assert_states(c, got, expected["state"])
    windowed = run_windowed(cut.spec, WindowPolicy(4096))
    assert windowed.start_time == point.time and windowed.start_step == point.step_index
    exact(windowed.final.state, result.final.state)
    assert windowed.final.step_index == result.final.step_index
    artifact = write_excision(tmp_path / "cut", cut)
    loaded = load_excision(artifact)
    assert loaded.spec == cut.spec
    write_run(tmp_path / "after-run", result)
    final = load_snapshot(tmp_path / "after-run/checkpoint_final")
    exact(final.checkpoint.state, result.final.state)
    exact(final.checkpoint.layout, result.final.layout)
    evidence(
        "excision-trajectory",
        dict(
            status="passed",
            source=raw,
            after=cut.spec.to_dict(),
            report=cut.report,
            diagnostics=result.diagnostics,
            timings=result.timings,
            window_timings=windowed.timings,
            max_error_over_budget=ratio,
            complete_final_snapshot=True,
        ),
        dict(actual=got, reference=expected["state"]),
    )


def test_compiled_two_world_batch_begins_at_cut_epoch():
    from cells.core.batch_windows import run_batch_windowed

    spec, point = prepared()
    spec = parse_spec(trajectory_definition())
    point = replace(point, step_index=EventGrid(spec).exact_index(point.time))
    cut = excise(spec, point, ["cell_1"])
    batch = BatchSpec((WorldSpec(3, cut.spec), WorldSpec(79, cut.spec)), 2, 200000, 2**31)
    c = reference.bind(cut.spec.to_dict())
    expected = reference.integrate(cut.spec.to_dict())
    samples = {3: [], 79: []}

    def collect(round):
        for identity, world in round.worlds.items():
            samples[identity].append(reference.flatten(c, vars(world.observations)))

    windowed = run_batch_windowed(batch, WindowPolicy(4096), sink=collect)
    for identity, window in windowed.worlds.items():
        assert window.start_time == point.time and window.start_step == point.step_index
        assert window.final.step_index == len(timeline(cut.spec)) - 1
        assert_states(c, np.concatenate(samples[identity]), expected["state"])
    # Bounded replay can also load the nonzero final checkpoints exactly.
    resumed = run_batch_windowed(batch, WindowPolicy(4096), windowed.checkpoints)
    for identity, world in resumed.worlds.items():
        exact(world.final.state, windowed.worlds[identity].final.state)
    evidence(
        "excision-batch",
        dict(
            status="passed",
            world_ids=[3, 79],
            absolute_start_time=point.time,
            source=spec.to_dict(),
            after=cut.spec.to_dict(),
            window_timings=windowed.timings,
        ),
    )
