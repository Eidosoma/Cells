"""Fixed physiological cadence, sealed association and atomic event-split loops."""

import json
from copy import deepcopy
from dataclasses import asdict, replace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_loop as loop
from cells.core import physiology_tissue_step as tissue
from cells.core.grid import EventGrid
from cells.core.runner import validate_checkpoint
from cells.core.schedule import event_index
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as view
from cells.processes import betse_perturbations as perturb
from tests.unit.test_physiology_permeability_view import exact_tree, fingerprints
from tests.unit.test_physiology_tissue_binding import component_state
from tests.unit.test_physiology_tissue_step import KINDS, case, control, evidence
from validation.tissue import physiology_tissue_loop_reference as reference


def inputs(kind="passive", engine="native", *, scale=0.5, at_event=True, end_loops=None):
    spec, point, binding, component, implementation = case(
        kind, at_event=at_event, source_dt_scale=scale
    )
    physiological_dt = spec.execution.dt / scale
    if end_loops is not None:
        raw = spec.to_dict()
        end = end_loops * physiological_dt
        raw["experiment"]["end_time"] = end
        raw["experiment"]["observation_times"] = sorted(
            {0.0, end, *(t for t in raw["experiment"]["observation_times"] if t <= end)}
        )
        spec = parse_spec(raw)
        binding = units.bind_tissue(spec, **json.loads(binding.inputs_json))
        component = component_state(binding)
        state, layout = implementation.initial_values(spec)
        point = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
    if engine == "native":
        rng = np.random.RandomState(17)
        rng.normal()  # Cached Gaussian must survive unrelated uniform component calls.
        rng = perturb._native_stream(rng.get_state(), np.__version__)
    else:
        rng = perturb.StableCoordinates(17, 7)
    stream = streams.new_stream(
        binding.component, rng, stream_id="atomic-loop", world_id=7, next_tick=31
    )
    current = component.diffusion.base_m2_s * (
        1.0
        + 0.03
        * np.arange(1, component.diffusion.base_m2_s.size + 1).reshape(
            component.diffusion.base_m2_s.shape
        )
    )
    component = replace(
        component,
        diffusion=component.diffusion._replace(
            scheduled_m2_s=current - component.diffusion.base_m2_s
        ),
        stream=stream,
        controls=replace(
            component.controls,
            phase="SIM",
            solver="normal",
            dynamic_enabled=True,
            protein_enabled=True,
            dynamic_level_mol_m2_s=1e-8,
            dt_s=physiological_dt,
        ),
        time_s=0.012,
        loop_calls=6,
    )
    cursor = loop.initialise(spec, point, binding, component)
    return spec, point, binding, component, cursor, implementation


def component_fields(component):
    return dict(
        protein=component.protein._asdict(),
        diffusion=component.diffusion._asdict(),
        controls=asdict(component.controls),
        time_s=component.time_s,
        loop_calls=component.loop_calls,
        stream_next_tick=component.stream.next_tick,
    )


def equal_component(actual, expected):
    exact_tree(actual.protein, expected.protein)
    exact_tree(actual.diffusion, expected.diffusion)
    assert actual.controls == expected.controls
    assert actual.time_s == expected.time_s and actual.loop_calls == expected.loop_calls
    assert streams.stream_record(actual.stream) == streams.stream_record(expected.stream)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("engine", ["native", "stable"])
def test_two_atomic_loops_match_exact_one_component_then_all_event_steps(kind, engine):
    spec, point, binding, component, cursor, _ = inputs(kind, engine)
    original_layout = point.layout
    for index in range(2):
        before = fingerprints(spec, point.state, point.layout, component)
        cursor_before = loop.cursor_record(cursor)
        transition = component_step.advance(component, binding.component)
        expected = point
        count = 0
        while expected.time < (index + 1) * component.controls.dt_s:
            expected = tissue.advance(spec, expected, binding, transition.state).checkpoint
            count += 1
        actual = loop.advance(spec, point, binding, component, cursor)
        exact_tree(actual.checkpoint.state, expected.state)
        equal_component(actual.component, transition.state)
        assert actual.checkpoint.layout is original_layout and actual.binding is binding
        assert len(actual.tissue_steps) == count == (3 if index == 0 else 2)
        assert actual.next_loop_index == actual.cursor.loop_index == index + 1
        assert actual.cursor.component_call_origin == 6
        assert actual.component.loop_calls == component.loop_calls + 1
        assert actual.component.stream.next_tick == component.stream.next_tick + 1
        assert actual.component.time_s == component.time_s + component.controls.dt_s
        assert actual.component.time_s != actual.checkpoint.time
        assert all(row.component is actual.component for row in actual.tissue_steps)
        assert fingerprints(spec, point.state, point.layout, component) == before
        assert loop.cursor_record(cursor) == cursor_before
        assert (
            loop.restore_cursor(
                loop.cursor_record(actual.cursor),
                spec,
                actual.checkpoint,
                binding,
                actual.component,
            )
            == actual.cursor
        )
        point, component, cursor = actual.checkpoint, actual.component, actual.cursor


@pytest.mark.parametrize("kind", KINDS)
def test_full_initial_and_evolved_loops_match_continuously_carried_independent_oracles(kind):
    spec, point, binding, component, cursor, implementation = inputs(kind)
    raw, record = spec.to_dict(), units.binding_record(binding)
    oracle = reference.tissue_reference.view.ORACLES[raw["model"]["id"]]
    standard_fields = tight_fields = point.state._asdict()
    standard_component = tight_component = component_fields(component)
    for index in range(2):
        actual = loop.advance(spec, point, binding, component, cursor)
        packet = actual.component_transition.packet.values
        standard = reference.advance(
            raw, standard_fields, record, standard_component, packet, loop_index=index
        )
        tight = reference.advance(
            raw, tight_fields, record, tight_component, packet, loop_index=index, refinement=2
        )
        runtime = view.evaluate(
            spec,
            point.state,
            point.layout,
            control(spec, point.time),
            binding,
            actual.component,
            step_s=spec.execution.dt,
        ).runtime_layout
        values = {
            key: []
            for key in (
                "actual",
                "standard",
                "oracle",
                "budget",
                "actual_phi",
                "standard_phi",
                "oracle_phi",
                "potential_budget",
                "state_error",
                "phi_error",
                "uncertainty",
                "phi_uncertainty",
            )
        }
        for local, normal, precise in zip(
            actual.tissue_steps, standard["intervals"], tight["intervals"], strict=True
        ):
            c, target = precise["context"], precise["state"]
            vector = oracle.flatten(c, local.checkpoint.state._asdict())
            budget = oracle.flatten(
                c,
                {
                    name: np.full(shape, 3e-23 if name.endswith("_C") else 3e-12)
                    for name, shape in c["shapes"].items()
                },
            ) + 3e-10 * np.abs(target)
            field = implementation.field_values(
                local.checkpoint.state, control(spec, local.checkpoint.time), runtime, xp=np
            )
            phi = np.r_[
                field.potential_V[: runtime.active.size][runtime.active],
                field.potential_V[runtime.active.size :][runtime.outside_active],
            ]
            phi_budget = 3e-13 + 3e-10 * np.abs(precise["endpoint_potential_V"])
            row = dict(
                actual=vector,
                standard=normal["state"],
                oracle=target,
                budget=budget,
                actual_phi=phi,
                standard_phi=normal["endpoint_potential_V"],
                oracle_phi=precise["endpoint_potential_V"],
                potential_budget=phi_budget,
                state_error=np.abs(vector - target) / budget,
                phi_error=np.abs(phi - precise["endpoint_potential_V"]) / phi_budget,
                uncertainty=np.abs(normal["state"] - target) / budget,
                phi_uncertainty=np.abs(
                    normal["endpoint_potential_V"] - precise["endpoint_potential_V"]
                )
                / phi_budget,
            )
            for key, value in row.items():
                values[key].append(value)
        arrays = {key: np.stack(value) for key, value in values.items()}
        errors = {
            key: float(np.max(arrays[key], initial=0))
            for key in ("state_error", "phi_error", "uncertainty", "phi_uncertainty")
        }
        evidence(
            "loop-reference-" + kind + "-" + str(index),
            dict(
                definition=raw,
                binding=record,
                standard_source_fields=standard_fields,
                tight_source_fields=tight_fields,
                standard_component=standard_component,
                tight_component=tight_component,
                production_source_fields=point.state._asdict(),
                production_source_component=component_fields(component),
                actual_component=component_fields(actual.component),
                prescribed_uniforms=packet,
                loop_index=index,
                source_times_s=[row.checkpoint.time for row in actual.tissue_steps],
                physiological_dt_s=component.controls.dt_s,
                tissue_dt_s=spec.execution.dt,
                errors=errors,
                cursor=loop.cursor_record(actual.cursor),
                scope=(
                    "Continuous own standard/tight DOP states across both complete loops; "
                    "no RK endpoint reseeding; prescribed packet under previously qualified RNG law"
                ),
            ),
            arrays,
        )
        assert errors["state_error"] <= 1 and errors["phi_error"] <= 1
        assert errors["uncertainty"] <= 0.1 and errors["phi_uncertainty"] <= 0.1
        for name, value in actual.component.protein._asdict().items():
            np.testing.assert_allclose(
                value, tight["component"]["protein"][name], rtol=5e-13, atol=2e-14
            )
        for name, value in actual.component.diffusion._asdict().items():
            np.testing.assert_allclose(
                value, tight["component"]["diffusion"][name], rtol=5e-13, atol=1e-30
            )
        assert actual.component.time_s == tight["component"]["time_s"]
        assert actual.component.loop_calls == tight["component"]["loop_calls"]
        assert actual.component.stream.next_tick == tight["component"]["stream_next_tick"]
        standard_fields, tight_fields = standard["fields"], tight["fields"]
        standard_component, tight_component = standard["component"], tight["component"]
        point, component, cursor = actual.checkpoint, actual.component, actual.cursor


@pytest.mark.parametrize("engine", ["native", "stable"])
def test_finer_tissue_grid_and_extra_event_substeps_never_retime_or_resample_component(engine):
    outputs = []
    for scale in (0.5, 0.25):
        spec, point, binding, component, cursor, _ = inputs(engine=engine, scale=scale)
        packets = []
        for _ in range(2):
            result = loop.advance(spec, point, binding, component, cursor)
            packets.append(result.component_transition.packet.values)
            point, component, cursor = result.checkpoint, result.component, result.cursor
        outputs.append((point, component, packets))
    a, b = outputs
    exact_tree(a[1].protein, b[1].protein)
    exact_tree(a[1].diffusion, b[1].diffusion)
    np.testing.assert_array_equal(a[2], b[2])
    assert a[0].time == b[0].time and a[0].step_index != b[0].step_index
    assert a[1].time_s == b[1].time_s and a[1].loop_calls == b[1].loop_calls
    assert streams.stream_record(a[1].stream)["rng"] == streams.stream_record(b[1].stream)["rng"]


@pytest.mark.parametrize("guard", ["INIT", "fast", "dynamic_off", "protein_off", "zero_level"])
def test_original_guards_and_enabled_zero_amplitude_have_one_fixed_duration_call(guard):
    spec, point, binding, component, _, _ = inputs()
    updates = {
        "INIT": dict(phase="INIT"),
        "fast": dict(solver="fast"),
        "dynamic_off": dict(dynamic_enabled=False),
        "protein_off": dict(protein_enabled=False),
        "zero_level": dict(dynamic_level_mol_m2_s=0.0),
    }
    component = replace(component, controls=replace(component.controls, **updates[guard]))
    cursor = loop.initialise(spec, point, binding, component)
    result = loop.advance(spec, point, binding, component, cursor)
    assert result.component.time_s == component.time_s + component.controls.dt_s
    assert result.component.loop_calls == component.loop_calls + 1
    active = guard == "zero_level"
    assert result.component.stream.next_tick == component.stream.next_tick + int(active)
    assert (result.component_transition.packet is not None) is active
    if not active:
        assert streams.stream_record(result.component.stream) == streams.stream_record(
            component.stream
        )
        exact_tree(result.component.protein, component.protein)
    else:
        np.testing.assert_array_equal(
            result.component.protein.cell_mol_m3, component.protein.cell_mol_m3
        )
    if guard == "INIT":
        exact_tree(result.component.diffusion, component.diffusion)


def test_protein_changes_are_explicitly_uncoupled_from_ordinary_numeric_charge():
    spec, point, binding, component, cursor, _ = inputs("fuel")
    changed = loop.advance(spec, point, binding, component, cursor)
    quiet = replace(component, controls=replace(component.controls, dynamic_level_mol_m2_s=0.0))
    unchanged = loop.advance(
        spec, point, binding, quiet, loop.initialise(spec, point, binding, quiet)
    )
    assert not np.array_equal(
        changed.component.protein.cell_mol_m3, unchanged.component.protein.cell_mol_m3
    )
    exact_tree(changed.checkpoint.state, unchanged.checkpoint.state)
    assert streams.stream_record(changed.component.stream) == streams.stream_record(
        unchanged.component.stream
    )


@pytest.mark.parametrize("index", [True, -1, 0.0, 2**64])
def test_cursor_rejects_implicit_or_out_of_range_indices(index):
    spec, point, binding, component, _, _ = inputs()
    with pytest.raises(ValueError, match="uint64"):
        loop.initialise(spec, point, binding, component, loop_index=index)


@pytest.mark.parametrize(
    "field",
    [
        "physiological_dt_s",
        "numeric_time_s",
        "numeric_step_index",
        "numeric_event_index",
        "component_time_s",
        "component_loop_calls",
        "component_call_origin",
        "stream_next_tick",
        "checkpoint_identity",
        "component_identity",
        "binding_identity",
        "source_definition_sha256",
    ],
)
def test_resealed_cursor_cannot_change_actual_complete_pair_association(field):
    spec, point, binding, component, cursor, _ = inputs()
    record = deepcopy(loop.cursor_record(cursor))
    if field.endswith("identity") or field.endswith("sha256"):
        record[field] = "f" * 64
    elif field == "numeric_time_s":
        record[field] = False  # Canonical field types matter even when False == 0.0.
    else:
        record[field] += 1
    record["identity"] = loop._digest(
        {key: value for key, value in record.items() if key != "identity"}
    )
    with pytest.raises(ValueError, match="association"):
        loop.restore_cursor(record, spec, point, binding, component)


def test_unknown_or_corrupt_cursor_fields_and_changed_valid_component_are_refused():
    spec, point, binding, component, cursor, _ = inputs()
    record = loop.cursor_record(cursor)
    record["extra"] = "unrecognized"
    record["identity"] = loop._digest(
        {key: value for key, value in record.items() if key != "identity"}
    )
    with pytest.raises(ValueError):
        loop.restore_cursor(record, spec, point, binding, component)
    with pytest.raises(ValueError):
        loop.cursor_record(replace(cursor, component_time_s=0.1))
    changed = replace(component, controls=replace(component.controls, dynamic_level_mol_m2_s=0.0))
    component_step.validate_state(changed, binding.component)
    with pytest.raises(ValueError, match="association"):
        loop.restore_cursor(loop.cursor_record(cursor), spec, point, binding, changed)


def test_cursor_pins_valid_numeric_state_bytes_and_replays_JAX_restored_layout():
    spec, point, binding, component, cursor, _ = inputs()
    restored = replace(
        point,
        state=jax.tree.map(jnp.asarray, point.state),
        layout=jax.tree.map(jnp.asarray, point.layout),
    )
    assert (
        loop.restore_cursor(loop.cursor_record(cursor), spec, restored, binding, component)
        == cursor
    )
    result = loop.advance(spec, restored, binding, component, cursor)
    assert result.checkpoint.layout is restored.layout
    state = result.checkpoint.state
    amount = state.amount_increment.copy()
    amount[0, 0] = np.nextafter(amount[0, 0], np.inf)
    changed = replace(result.checkpoint, state=state._replace(amount_increment=amount))
    validate_checkpoint(spec, changed, times=EventGrid(spec))
    with pytest.raises(ValueError, match="association"):
        loop.restore_cursor(
            loop.cursor_record(result.cursor), spec, changed, binding, result.component
        )


@pytest.mark.parametrize("horizon", [1.0, 1.5])
def test_terminal_or_partial_next_nominal_interval_refuses_before_any_component_call(
    horizon, monkeypatch
):
    spec, point, binding, component, cursor, _ = inputs(end_loops=horizon)
    result = loop.advance(spec, point, binding, component, cursor)
    assert (
        loop.restore_cursor(
            loop.cursor_record(result.cursor), spec, result.checkpoint, binding, result.component
        )
        == result.cursor
    )

    def forbidden(*args, **kwargs):
        pytest.fail("Terminal/partial loop admission performed a component call")

    with monkeypatch.context() as guard:
        guard.setattr(component_step, "advance", forbidden)
        with pytest.raises(loop.TissueLoopRejected) as caught:
            loop.advance(spec, result.checkpoint, binding, result.component, result.cursor)
    assert caught.value.stage == "cursor_admission"
    assert caught.value.proposed_component is None and not caught.value.tissue_steps
    assert caught.value.packet is None


def test_unrepresented_boundary_and_mid_loop_cursor_refuse_without_retaping(monkeypatch):
    spec, point, binding, component, cursor, _ = inputs(at_event=False)
    component = replace(
        component, controls=replace(component.controls, dt_s=0.75 * component.controls.dt_s)
    )
    cursor = loop.initialise(spec, point, binding, component)

    def forbidden(*args, **kwargs):
        pytest.fail("An unrepresented nominal boundary performed a component call")

    with monkeypatch.context() as guard:
        guard.setattr(component_step, "advance", forbidden)
        with pytest.raises(loop.TissueLoopRejected) as caught:
            loop.advance(spec, point, binding, component, cursor)
    assert caught.value.stage == "cursor_admission" and caught.value.packet is None
    spec, point, binding, component, cursor, _ = inputs()
    result = loop.advance(spec, point, binding, component, cursor)
    middle = result.tissue_steps[0].checkpoint
    for index in (0, 1):
        with pytest.raises(ValueError, match="left boundary"):
            loop.initialise(spec, middle, binding, result.component, loop_index=index)


@pytest.mark.parametrize("failure", ["before_draw", "after_draw"])
def test_component_failure_retains_exact_proposed_tape_and_no_numeric_steps(failure):
    spec, point, binding, component, _, _ = inputs()
    if failure == "before_draw":
        component = replace(
            component,
            diffusion=component.diffusion._replace(
                scheduled_m2_s=-2 * component.diffusion.base_m2_s
            ),
        )
    else:
        component = replace(
            component,
            protein=perturb.ProteinState(*(np.zeros_like(value) for value in component.protein)),
        )
    cursor = loop.initialise(spec, point, binding, component)
    before = fingerprints(spec, point.state, point.layout, component)
    with pytest.raises(loop.TissueLoopRejected) as caught:
        loop.advance(spec, point, binding, component, cursor)
    error = caught.value
    assert error.stage == "component_transition" and error.component_rejection is not None
    assert error.proposed_component is error.component_rejection.trial
    assert error.proposed_stream is error.component_rejection.stream
    assert not error.tissue_steps and error.failed_tissue_step is None
    assert (error.packet is not None) is (failure == "after_draw")
    if error.packet is not None:
        expected, stream = streams.draw(component.stream, binding.component, site="protein_flux")
        np.testing.assert_array_equal(error.packet.values, expected.values)
        assert streams.stream_record(error.proposed_stream) == streams.stream_record(stream)
    assert fingerprints(spec, point.state, point.layout, component) == before
    evidence(
        "loop-component-rejected-" + failure,
        dict(
            stage=error.stage,
            component_stage=error.component_rejection.stage,
            draw_consumed=error.packet is not None,
            input_cursor=loop.cursor_record(cursor),
            proposed_component=component_fields(error.proposed_component),
        ),
    )


def test_later_numeric_failure_retains_proposed_component_rng_completed_step_and_raw_trial(
    monkeypatch,
):
    spec, point, binding, component, cursor, implementation = inputs()
    before = fingerprints(spec, point.state, point.layout, component)
    cursor_before = loop.cursor_record(cursor)
    original = tissue.array_rk4_step
    calls = 0

    def trial(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            with monkeypatch.context() as failure:
                failure.setattr(implementation, "domain_valid", lambda *a, **k: np.asarray(False))
                return original(*args, **kwargs)
        return original(*args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(tissue, "array_rk4_step", trial)
        with pytest.raises(loop.TissueLoopRejected) as caught:
            loop.advance(spec, point, binding, component, cursor)
    error = caught.value
    assert calls == 2 and error.stage == "tissue_substeps"
    assert len(error.tissue_steps) == 1 and error.failed_tissue_step is not None
    assert error.failed_tissue_step.source_checkpoint is error.tissue_steps[0].checkpoint
    assert error.failed_tissue_step.trial is not None
    assert error.proposed_component is error.component_transition.state
    assert error.proposed_component.loop_calls == component.loop_calls + 1
    assert error.proposed_stream.next_tick == component.stream.next_tick + 1
    assert error.packet is error.component_transition.packet
    assert fingerprints(spec, point.state, point.layout, component) == before
    assert loop.cursor_record(cursor) == cursor_before
    evidence(
        "loop-numeric-rejected",
        dict(
            stage=error.stage,
            completed_tissue_steps=1,
            input_cursor=cursor_before,
            proposed_component=component_fields(error.proposed_component),
            prescribed_uniforms=error.packet.values,
            failed_status=[row._asdict() for row in error.failed_tissue_step.trial.status],
        ),
        {
            "failed_stage0__" + key: value
            for key, value in error.failed_tissue_step.trial.stages[0]._asdict().items()
        },
    )
