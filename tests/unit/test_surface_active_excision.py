"""Actual gate memory, all nineteen histories and conservative active continuation."""

import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from cells.core.active_tissue_excision import GATES, capture_source, decode_source, physical
from cells.core.batch import BatchSpec, WorldSpec
from cells.core.errors import NumericalError
from cells.core.excision import excise
from cells.core.grid import EventGrid
from cells.core.runner import run, timeline, validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import Checkpoint, initialise
from cells.core.surface_active_excision_spec import base_spec
from cells.core.windows import WindowPolicy, iter_windows, plan_windows, run_windowed
from cells.excision_io import ACTIVE_KIND, KIND, load_excision, write_excision
from cells.io import load_snapshot, write_run, write_snapshot
from cells.models import surface_active_excision as model
from cells.models import surface_hcn_extra as parent
from cells.models.registry import get_model
from cells.numerics.fixed_step import rk4_step
from tests.unit.test_surface_catalog import evidence
from tests.unit.test_surface_kinetic import assert_states, exact
from validation.tissue import active_excision_fixtures as fixtures
from validation.tissue import active_excision_reference as reference

TRAJECTORY_REFINEMENT = 32
CONTROL_FAMILIES = ("membrane", "junction", "channel", "pump")


def trajectory_definition():
    raw = fixtures.definition(padded=True)
    raw["execution"].update(
        dt=fixtures.DT / TRAJECTORY_REFINEMENT, max_steps=10000, max_trace_bytes=2**30
    )
    return raw


@lru_cache(maxsize=12)
def source_reference(arm):
    return reference.integrate(fixtures.definition(arm), end_time=fixtures.CUT_TIME)


@lru_cache(maxsize=24)
def prepared(arm="open", padded=True):
    raw = fixtures.definition(arm, padded=padded)
    spec = parse_spec(raw)
    c = reference.bind(raw)
    state, layout = parent.initial_values(spec)
    for key, value in reference.unpack(c, source_reference(arm)["state"][-1]).items():
        getattr(state, key)[tuple(slice(0, n) for n in value.shape)] = value
    time = fixtures.CUT_TIME
    point = Checkpoint(
        state, layout, time, EventGrid(spec).exact_index(time), event_index(spec, time)
    )
    parent.check_values(state, spec)
    return spec, point


def compare_transition(spec, point, cut):
    c = reference.bind(spec.to_dict())
    expected = reference.excise(
        spec.to_dict(),
        reference.flatten(c, point.state._asdict()),
        cut.report["removed_cell_ids"],
        point.time,
    )
    if cut.spec is None:
        assert expected["raw"] is None
        return dict(terminal=True)
    c = reference.bind(cut.spec.to_dict())
    y = reference.flatten(c, cut.checkpoint.state._asdict())
    np.testing.assert_array_equal(y, expected["state"])
    table = control_values(cut.spec, [point.time])
    control = type(table)(*(v[0] for v in table))
    impl = get_model(cut.spec.model)
    got = impl.rhs(
        cut.checkpoint.state, control, cut.checkpoint.layout, cut.checkpoint.layout.active, xp=np
    )
    target, _, _ = reference.evaluate(c, y, point.time)
    ratio = assert_states(
        c, reference.flatten(c, got._asdict()), target, atol=3e-12, charge_atol=3e-23, rtol=3e-10
    )
    if cut.report["changed"]:
        np.testing.assert_allclose(
            np.asarray(cut.report["removed_amount_fmol"]).sum(axis=-1),
            expected["audit"]["removed_amount_fmol"],
            atol=2e-11,
            rtol=3e-12,
        )
        for actual, independent in (
            ("unresolved_cut_energy_pJ", "unresolved_cut_energy_pJ"),
            ("held_boundary_work_impulse_pJ", "maintained_boundary_work_pJ"),
        ):
            np.testing.assert_allclose(
                cut.report[actual], expected["audit"][independent], atol=2e-10, rtol=3e-9
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


@pytest.mark.parametrize(
    "arm",
    [
        "open",
        "clamped",
        "blocked",
        "no-op",
        "single-survivor",
        "reordered",
        "empty",
    ],
)
@pytest.mark.parametrize("padded", [False, True])
def test_nonzero_active_cut_preserves_physics_gates_and_complete_source(arm, padded):
    spec, point = prepared(arm, padded)
    untouched = tuple(np.array(v) for v in (*point.state, *point.layout))
    cut = excise(spec, point, fixtures.cut_plan(arm)[0]["removed_cell_ids"])
    checked = compare_transition(spec, point, cut)
    exact(untouched, (*point.state, *point.layout))
    assert cut.spec == parse_spec(cut.spec.to_dict())
    assert cut.checkpoint.time == point.time
    assert len(cut.checkpoint.state) == 19
    if arm == "no-op":
        assert cut.spec == spec and cut.checkpoint is point
        exact(cut.checkpoint.state, point.state)
    else:
        assert get_model(cut.spec.model) is model
        assert type(cut.checkpoint.layout) is parent.LAYOUT_TYPE
        assert all(
            not np.any(getattr(cut.checkpoint.state, k)) for k in model.STATE_AXES if k not in GATES
        )
        assert set(cut.report["archived_retained_state"]) == set(model.STATE_AXES)
        assert set(cut.report["archived_removed_state"]) == set(model.STATE_AXES)
        restored_spec, restored = decode_source(capture_source(spec, point))
        assert restored_spec == spec
        exact(restored.state, point.state)
        exact(restored.layout, point.layout)
    evidence(
        "active-excision-stage-" + arm + "-" + str(padded),
        dict(
            status="passed",
            source=spec.to_dict(),
            report=cut.report,
            comparison=checked,
        ),
    )


@pytest.mark.parametrize("removed", [["cell_0"], ["cell_1"], ["cell_2"]])
@pytest.mark.parametrize("reordered", [False, True])
def test_all_fifty_six_laws_keep_owner_specific_gate_layout_and_stage(removed, reordered):
    raw = fixtures.definition("reordered" if reordered else "open", catalog="full", padded=True)
    spec = parse_spec(raw)
    point = initialise(spec)
    cut = excise(spec, point, removed)
    checked = compare_transition(spec, point, cut)
    assert len({v.kinetic_law for v in spec.model.channels}) == 56
    expected = {
        v.id: v
        for v in spec.model.channels
        if v.membrane_id in {m.id for m in cut.spec.model.membranes}
    }
    assert {v.id: v for v in cut.spec.model.channels} == expected
    evidence(
        "active-excision-full-catalog-" + removed[0] + "-" + str(reordered),
        dict(
            status="passed",
            source=raw,
            report=cut.report,
            comparison=checked,
            scope="Stage ownership across 56 laws; not 56 independent tissue trajectories",
        ),
    )


@pytest.mark.parametrize("arm", ["closed", "disconnected"])
def test_incompatible_retained_fields_leave_active_source_untouched(arm):
    spec, point = prepared(arm)
    previous = tuple(np.array(v) for v in (*point.state, *point.layout))
    with pytest.raises((ConfigError, NumericalError)):
        excise(spec, point, fixtures.cut_plan(arm)[0]["removed_cell_ids"])
    exact(previous, (*point.state, *point.layout))


@pytest.mark.parametrize("fault", ["time", "event", "step", "shape", "nan", "unknown", "duplicate"])
def test_invalid_active_source_clock_state_or_selection_is_rejected(fault):
    spec, point = prepared()
    ids = ["cell_1"]
    if fault == "time":
        point = replace(point, time=point.time + 1e-9)
    elif fault == "event":
        point = replace(point, event_index=point.event_index + 1)
    elif fault == "step":
        point = replace(point, step_index=point.step_index + 1)
    elif fault == "shape":
        point = replace(point, state=point.state._replace(pump_cycles=np.zeros((1, 1))))
    elif fault == "nan":
        point = replace(
            point,
            state=point.state._replace(pump_cycles=np.full_like(point.state.pump_cycles, np.nan)),
        )
    elif fault == "unknown":
        ids = ["absent"]
    else:
        ids *= 2
    with pytest.raises((ConfigError, NumericalError)):
        excise(spec, point, ids)


@pytest.mark.parametrize(
    "fault",
    [
        "gate",
        "pump",
        "source_gate",
        "source_history",
        "source_layout",
        "integer_overflow",
        "boolean_type",
        "state_type",
        "dt",
        "lost_clock",
        "past_channel",
        "past_pump",
        "past_junction",
        "policy",
        "inventory",
        "past_observation",
    ],
)
def test_cut_definition_refuses_altered_gate_owners_clocks_or_provenance(fault):
    spec, point = prepared()
    raw = excise(spec, point, ["cell_1"]).spec.to_dict()
    m, e = raw["model"], raw["experiment"]
    state = m["excision"]["source"]["checkpoint"]["state"]
    layout = m["excision"]["source"]["checkpoint"]["layout"]
    if fault == "gate":
        m["tissue"]["channels"][0]["initial_gate"][0] = 0.0
    elif fault == "pump":
        m["tissue"]["membranes"][0]["pump"]["capacity_fmol_per_s"] *= 2
    elif fault == "source_gate":
        state["channel_gate"][0][0] = 1.1
    elif fault == "source_history":
        del state["metabolic_work_pJ"]
    elif fault == "source_layout":
        layout["volume"][0] *= 2
    elif fault == "integer_overflow":
        key = next(k for k, v in point.layout._asdict().items() if v.dtype == np.int32 and v.size)
        a = np.asarray(layout[key], dtype=np.int64)
        a.flat[0] += 2**32
        layout[key] = a.tolist()
    elif fault == "boolean_type":
        layout["active"][0] = 1
    elif fault == "state_type":
        state["pump_cycles"][0] = "0"
    elif fault == "dt":
        raw["execution"]["dt"] /= 2
    elif fault == "lost_clock":
        for kind in CONTROL_FAMILIES:
            for row in e[kind + "_controls"]:
                row["schedule"] = [v for v in row["schedule"] if v["time"] != 93.7e-6]
    elif fault.startswith("past_") and fault != "past_observation":
        e[fault.removeprefix("past_") + "_controls"][0]["schedule"][0]["availability"] = 0.0
    elif fault == "policy":
        m["excision"]["state_policy"] = "reset_all_gates"
    elif fault == "inventory":
        m["tissue"]["cells"][0]["initial_amount_fmol"]["Ca"] += 0.1
    else:
        e["observation_times"].insert(0, 0.0)
    with pytest.raises((ConfigError, NumericalError)):
        parse_spec(raw)


def test_surviving_channels_evolve_while_blocked_and_removed_clocks_remain():
    spec, point = prepared("blocked")
    original, _ = parent.initial_values(spec)
    assert np.max(np.abs(point.state.channel_gate - original.channel_gate)) > 1e-3
    assert np.max(np.abs(point.state.junction_gate - original.junction_gate)) > 1e-5
    assert all(not np.any(getattr(point.state, k)) for k in model.STATE_AXES if k not in GATES)
    cut = excise(spec, point, ["cell_1"])
    assert {v.time for v in spec.experiment.changes} <= {
        v.time for v in cut.spec.experiment.changes
    }
    created = initialise(cut.spec)
    exact(created.state, cut.checkpoint.state)
    assert created.time == point.time
    altered = created.state._replace(channel_gate=np.array(created.state.channel_gate))
    altered.channel_gate[0, 0] += 1e-5
    with pytest.raises(ConfigError, match="initial state"):
        validate_checkpoint(cut.spec, replace(created, state=altered))


@pytest.mark.parametrize("gate", [0.4, 0.8])
def test_active_cut_field_uses_intrinsic_junction_gate_in_floating_components(gate):
    from cells.models import surface_tissue as passive

    raw = json.loads(
        (Path(__file__).parents[2] / "configs/resolved_hcn_extra_ionic.json").read_text()
    )
    spec = parse_spec(raw)
    original = initialise(spec)
    state = original.state._replace(junction_gate=np.array(original.state.junction_gate))
    state.junction_gate[0] = gate
    # A manufactured admissible state, not a claim of an integrated prefix.
    time = 1.25e-6
    point = replace(
        original,
        state=state,
        time=time,
        step_index=EventGrid(spec).exact_index(time),
        event_index=event_index(spec, time),
    )
    capture_source(spec, point)
    c = reference.bind(raw)
    _, expected, _ = reference.evaluate(c, reference.flatten(c, state._asdict()), time)
    actual = physical(spec, point)["potential"]
    packed = np.r_[
        actual[: len(spec.model.cells)],
        actual[len(point.layout.active) : len(point.layout.active) + len(spec.model.extracellular)],
    ]
    np.testing.assert_allclose(packed, expected, atol=3e-13, rtol=3e-10)
    table = control_values(spec, [time])
    control = type(table)(*(v[0] for v in table))
    ungated = passive.field_values(state, control, point.layout, xp=np).potential_V
    assert np.max(np.abs(actual - ungated)) > 1e-5
    cut = excise(spec, point, [])
    assert cut.checkpoint is point
    evidence(
        "active-excision-floating-field-" + str(gate),
        dict(
            status="passed",
            source=raw,
            intrinsic_gate=gate,
            actual_potential_V=packed.tolist(),
            independent_potential_V=expected.tolist(),
            error_if_intrinsic_gate_ignored_V=float(np.max(np.abs(actual - ungated))),
            scope="Manufactured floating-component field control; not an evolved tissue case",
        ),
    )


@pytest.mark.parametrize("selection", [["cell_1"], [], ["cell_0", "cell_1", "cell_2"]])
def test_active_excision_roundtrip_and_family_checksum(tmp_path, selection):
    spec, point = prepared()
    cut = excise(spec, point, selection)
    path = write_excision(tmp_path / "cut", cut)
    loaded = load_excision(path)
    assert loaded.spec == cut.spec and loaded.report == cut.report
    exact(loaded.source_checkpoint.state, point.state)
    exact(loaded.source_checkpoint.layout, point.layout)
    if cut.checkpoint is not None:
        exact(loaded.checkpoint.state, cut.checkpoint.state)
        exact(loaded.checkpoint.layout, cut.checkpoint.layout)
    else:
        assert compare_transition(spec, point, cut)["terminal"]
        assert set(cut.report["archived_removed_state"]) == set(model.STATE_AXES)
    manifest = json.loads((path / "manifest.json").read_text())
    assert manifest["kind"] == ACTIVE_KIND
    manifest["kind"] = KIND
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ConfigError, match="family"):
        load_excision(path)


def test_sequential_same_time_cuts_keep_nested_active_history_and_exact_gates():
    spec, point = prepared()
    first = excise(spec, point, ["cell_1"])
    second = excise(first.spec, first.checkpoint, ["cell_0"])
    combined = excise(spec, point, ["cell_0", "cell_1"])
    assert base_spec(second.spec).model == base_spec(combined.spec).model
    exact(second.checkpoint.state, combined.checkpoint.state)
    assert second.checkpoint.time == point.time
    previous = json.loads(second.spec.model.excision_json)["source"]["definition"]
    assert previous["model"]["excision"]["source"] == capture_source(spec, point)


def test_sequential_nonzero_epoch_archives_evolved_active_ledgers_and_gates():
    spec, point = prepared()
    first = excise(spec, point, ["cell_1"])
    time = fixtures.cut_plan("sequential")[1]["time_s"]
    c = reference.bind(first.spec.to_dict())
    target = reference.integrate(first.spec.to_dict(), end_time=time)
    state, layout = model.initial_values(first.spec)
    for key, value in reference.unpack(c, target["state"][-1]).items():
        getattr(state, key)[tuple(slice(0, n) for n in value.shape)] = value
    evolved = Checkpoint(
        state, layout, time, EventGrid(first.spec).exact_index(time), event_index(first.spec, time)
    )
    assert np.max(np.abs(state.pump_cycles)) > 0
    assert np.max(np.abs(state.channel_gate - first.checkpoint.state.channel_gate)) > 1e-3
    second = excise(first.spec, evolved, ["cell_0"])
    checked = compare_transition(first.spec, evolved, second)
    archived = json.loads(second.spec.model.excision_json)["source"]
    assert archived == capture_source(first.spec, evolved)
    assert second.checkpoint.time == time
    assert second.report["retained_cell_ids"] == ["cell_2"]
    evidence(
        "active-excision-sequential-evolved",
        dict(
            status="passed",
            source=spec.to_dict(),
            after=second.spec.to_dict(),
            comparison=checked,
            scope="Second adapter cut from an independently evolved complete19 checkpoint",
        ),
    )


def test_active_cli_writes_reusable_snapshot(tmp_path, capsys):
    from cells.__main__ import main

    spec, point = prepared()
    write_snapshot(tmp_path / "before", spec, point)
    assert (
        main(
            [
                "excise",
                str(tmp_path / "before"),
                "--remove",
                "cell_1",
                "--output",
                str(tmp_path / "cut"),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
    loaded = load_excision(tmp_path / "cut")
    assert loaded.checkpoint.time == point.time
    assert len(loaded.checkpoint.state) == 19


def test_zero_remaining_active_epoch_and_window_planning():
    from cells.core.batch_windows import plan_batch_windows, run_batch_windowed

    spec, point = prepared()
    cut = excise(spec, point, ["cell_1"])
    raw = cut.spec.to_dict()
    raw["experiment"].update(end_time=point.time, observation_times=[point.time])
    for kind in CONTROL_FAMILIES:
        for row in raw["experiment"][kind + "_controls"]:
            row["schedule"] = [v for v in row["schedule"] if v["time"] <= point.time]
    finished = parse_spec(raw)
    plan = plan_windows(finished, WindowPolicy(64))
    assert plan.window_count == 1 and plan.start_step == point.step_index
    scalar = run_windowed(finished)
    assert scalar.start_time == scalar.final.time == point.time
    assert scalar.resources["executed_steps"] == 0
    exact(scalar.final.state, cut.checkpoint.state)
    batch = BatchSpec((WorldSpec(3, finished), WorldSpec(79, finished)), 2, 2048, 2**30)
    assert all(
        v.start_step == point.step_index for v in plan_batch_windows(batch, WindowPolicy(64)).worlds
    )
    result = run_batch_windowed(batch)
    for world in result.worlds.values():
        assert world.start_time == world.final.time == point.time
        assert world.resources["executed_steps"] == 0
        exact(world.final.state, cut.checkpoint.state)


def test_offline_one_four_sixteen_gpu_placement_keeps_active_provenance():
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
        "active-excision-offline-plans",
        dict(
            status="passed",
            inputs=raw,
            plans=plans,
            scope="Offline placement, noGPU execution claim",
        ),
    )


@pytest.mark.parametrize("phase", ["before", "after"])
def test_host_active_transient_refines_without_changing_rates_or_tolerances(phase):
    if phase == "before":
        spec = parse_spec(fixtures.definition())
        point = initialise(spec)
        point = replace(
            point,
            state=type(point.state)(*(np.asarray(v) for v in point.state)),
            layout=type(point.layout)(*(np.asarray(v) for v in point.layout)),
        )
    else:
        source, old = prepared(padded=False)
        cut = excise(source, old, ["cell_1"])
        spec, point = cut.spec, cut.checkpoint
    c = reference.bind(spec.to_dict())
    times = [point.time, point.time + fixtures.DT, point.time + 2 * fixtures.DT]
    expected = reference.integrate(
        spec.to_dict(), start_time=point.time, end_time=times[-1], observation_times=times
    )
    impl, p = get_model(spec.model), point.layout
    table = control_values(spec, [point.time])
    control = type(table)(*(v[0] for v in table))

    def rhs(y, u, p, active):
        assert impl.control_domain_valid(y, u, p, active, xp=np)
        return impl.rhs(y, u, p, active, xp=np)

    arrays, errors = {}, []
    for refinement in (8, 16, TRAJECTORY_REFINEMENT):
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
                    np.abs(actual - expected["state"])
                    / (budgets + 3e-9 * np.abs(expected["state"]))
                )
            )
        )
        arrays[str(refinement)] = actual
    evidence(
        "active-excision-transient-" + phase,
        dict(
            status="measured",
            input=spec.to_dict(),
            times=times,
            refinements=[8, 16, TRAJECTORY_REFINEMENT],
            max_error_over_budget=errors,
        ),
        dict(reference=expected["state"], **arrays),
    )
    assert errors[-1] <= 1
    assert errors[-1] < max(errors[0] / 8, 0.01)


def test_compiled_active_prefix_cut_suffix_and_complete_restart(tmp_path):
    raw = trajectory_definition()
    original = parse_spec(raw)
    before = next(
        iter_windows(original, WindowPolicy(EventGrid(original).exact_index(fixtures.CUT_TIME)))
    )
    point = before.checkpoint_at(fixtures.CUT_TIME)
    c0 = reference.bind(raw)
    prefix = reference.integrate(raw, end_time=point.time)
    prefix_ratio = assert_states(
        c0, reference.flatten(c0, vars(before.observations)), prefix["state"]
    )
    cut = excise(before.spec, point, ["cell_1"])
    result = run(cut.spec)
    assert result.times[0] == point.time and result.start_step == point.step_index
    c = reference.bind(cut.spec.to_dict())
    expected = reference.integrate(cut.spec.to_dict())
    got = reference.flatten(c, vars(result.observations))
    ratio = assert_states(c, got, expected["state"])
    windowed = run_windowed(cut.spec, WindowPolicy(512))
    exact(windowed.final.state, result.final.state)
    assert windowed.final.step_index == result.final.step_index
    loaded = load_excision(write_excision(tmp_path / "cut", cut))
    assert loaded.spec == cut.spec
    write_run(tmp_path / "after-run", result)
    final = load_snapshot(tmp_path / "after-run/checkpoint_final")
    exact(final.checkpoint.state, result.final.state)
    exact(final.checkpoint.layout, result.final.layout)
    evidence(
        "active-excision-trajectory",
        dict(
            status="passed",
            source=raw,
            after=cut.spec.to_dict(),
            report=cut.report,
            diagnostics=result.diagnostics,
            timings=result.timings,
            window_timings=windowed.timings,
            prefix_max_error_over_budget=prefix_ratio,
            max_error_over_budget=ratio,
            complete_final_snapshot=True,
        ),
        dict(actual=got, reference=expected["state"]),
    )


def test_compiled_active_two_world_batch_absolute_epoch_and_resume():
    from cells.core.batch_windows import run_batch_windowed

    _, point = prepared()
    spec = parse_spec(trajectory_definition())
    point = replace(point, step_index=EventGrid(spec).exact_index(point.time))
    cut = excise(spec, point, ["cell_1"])
    batch = BatchSpec((WorldSpec(3, cut.spec), WorldSpec(79, cut.spec)), 2, 10000, 2**30)
    c = reference.bind(cut.spec.to_dict())
    expected = reference.integrate(cut.spec.to_dict())
    samples = {3: [], 79: []}

    def collect(round):
        for identity, world in round.worlds.items():
            samples[identity].append(reference.flatten(c, vars(world.observations)))

    result = run_batch_windowed(batch, WindowPolicy(512), sink=collect)
    ratios = {}
    for identity, world in result.worlds.items():
        assert world.start_time == point.time and world.start_step == point.step_index
        assert world.final.step_index == len(timeline(cut.spec)) - 1
        ratios[str(identity)] = assert_states(
            c, np.concatenate(samples[identity]), expected["state"]
        )
    resumed = run_batch_windowed(batch, WindowPolicy(512), result.checkpoints)
    for identity, world in resumed.worlds.items():
        exact(world.final.state, result.worlds[identity].final.state)
    evidence(
        "active-excision-batch",
        dict(
            status="passed",
            world_ids=[3, 79],
            source=spec.to_dict(),
            after=cut.spec.to_dict(),
            window_timings=result.timings,
            max_error_over_budget=ratios,
        ),
    )


def test_compiled_full_catalog_retains_static_law_dispatch_and_world_domains():
    import jax
    import jax.numpy as jnp

    spec = parse_spec(fixtures.definition(catalog="full", padded=True))
    cut = excise(spec, initialise(spec), ["cell_1"])
    y, p = cut.checkpoint.state, cut.checkpoint.layout
    table = control_values(cut.spec, [0.0])
    u = type(table)(*(v[0] for v in table))
    invalid = y._replace(channel_gate=np.array(y.channel_gate))
    invalid.channel_gate[0, 0] = 1.1
    worlds = type(y)(*(jnp.asarray(np.stack([a, b])) for a, b in zip(y, invalid, strict=True)))

    def evaluate(state, control, layout):
        valid = model.control_domain_valid(state, control, layout, layout.active)
        return model.rhs(state, control, layout, layout.active), valid

    actual, valid = jax.device_get(
        jax.jit(jax.vmap(evaluate, in_axes=(0, None, None)))(worlds, u, p)
    )
    np.testing.assert_array_equal(valid, [True, False])
    c = reference.bind(cut.spec.to_dict())
    expected, _, _ = reference.evaluate(c, reference.flatten(c, y._asdict()), 0.0)
    ratio = assert_states(
        c,
        reference.flatten(c, {k: v[0] for k, v in actual._asdict().items()}),
        expected,
        atol=3e-12,
        charge_atol=3e-23,
        rtol=3e-10,
    )
    evidence(
        "active-excision-compiled-catalog",
        dict(
            status="passed",
            source=spec.to_dict(),
            after=cut.spec.to_dict(),
            max_error_over_budget=ratio,
            domain_valid=valid.tolist(),
            scope="Compiled stage/domain comparison; not a full-catalog long trajectory",
        ),
    )
