"""Accepted original-grid tissue steps and independent full held-P intervals."""

import json
import os
from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_perturbation_step as component_step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_step as tissue
from cells.core.grid import EventGrid
from cells.core.runner import validate_checkpoint
from cells.core.schedule import control_values, event_index
from cells.core.specs import parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as view
from cells.numerics.fixed_step import rk4_step
from cells.processes import betse_perturbations as perturb
from tests.unit.test_physiology_permeability_view import exact_tree, fingerprints
from tests.unit.test_physiology_tissue_binding import arguments, component_state, definition
from validation.tissue import physiology_tissue_step_reference as reference

KINDS = ("passive", "ionic", "calcium", "fuel")


class EndpointPotentialAccuracyError(AssertionError):
    """The declared RK trajectory exceeds the unchanged endpoint phi budget."""


def evidence(name, record, arrays=None):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        folder = Path(directory) / "tissue-step"
        folder.mkdir(parents=True, exist_ok=True)

        def safe(value):
            if isinstance(value, dict):
                return {key: safe(item) for key, item in value.items()}
            if isinstance(value, (tuple, list)):
                return [safe(item) for item in value]
            if isinstance(value, (np.ndarray, np.generic)):
                return safe(np.asarray(value).tolist())
            if isinstance(value, float) and not np.isfinite(value):
                return str(value)
            return value

        (folder / (name + ".json")).write_text(
            json.dumps(safe(record), indent=2, allow_nan=False) + "\n"
        )
        if arrays is not None:
            np.savez_compressed(folder / (name + ".npz"), **arrays)


def case(kind="passive", *, changed=True, at_event=False, source_dt_scale=1.0):
    raw = definition(kind, padded=not at_event, reorder=at_event)
    if at_event:
        event = 0.75 * raw["execution"]["dt"]
        control = raw["experiment"]["membrane_controls"][0]
        control["schedule"].append(dict(time=event, availability=0.35))
        raw["experiment"]["observation_times"] = sorted(
            {*raw["experiment"]["observation_times"], event}
        )
    # Declare any numerical refinement before binding, initialization or evolution.
    # Physical source geometry, horizon and absolute schedule events stay exact.
    raw["execution"]["dt"] *= source_dt_scale
    spec = parse_spec(raw)
    args = arguments(spec, reverse=True)
    args["membrane_thickness_m"] = {
        row.id: 2.0 ** (-28 - i % 3) for i, row in enumerate(spec.model.membranes)
    }
    binding = units.bind_tissue(spec, **args)
    component = component_state(binding)
    factor = 1.0
    if changed:
        factor = 1.0 + 0.03 * np.arange(1, component.diffusion.base_m2_s.size + 1).reshape(
            component.diffusion.base_m2_s.shape
        )
    component = replace(
        component,
        controls=replace(component.controls, phase="SIM"),
        diffusion=component.diffusion._replace(current_m2_s=component.diffusion.base_m2_s * factor),
    )
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    point = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
    return spec, point, binding, component, implementation


def control(spec, time):
    table = control_values(spec, [time])
    return type(table)(*(value[0] for value in table))


@pytest.mark.parametrize(
    "kind,at_event",
    [
        pytest.param(
            kind,
            at_event,
            id=str(at_event) + "-" + kind,
            marks=(
                pytest.mark.xfail(
                    strict=True,
                    raises=EndpointPotentialAccuracyError,
                    reason="Original passive 100us source dt exceeds trajectory-phi budget",
                )
                if kind == "passive" and not at_event
                else ()
            ),
        )
        for at_event in (False, True)
        for kind in KINDS
    ],
)
def test_full_declared_initial_and_evolved_intervals_match_refined_held_P_oracle(kind, at_event):
    spec, point, binding, component, implementation = case(kind, at_event=at_event)
    raw, record = spec.to_dict(), units.binding_record(binding)
    original_layout = point.layout
    trajectory_potential_errors = []
    for index in range(2):
        before = fingerprints(spec, point.state, point.layout, component)
        result = tissue.advance(spec, point, binding, component)
        after, h = result.checkpoint, result.checkpoint.time - point.time
        standard = reference.integrate(
            raw,
            point.state._asdict(),
            record,
            component.diffusion.current_m2_s,
            start_time_s=point.time,
            end_time_s=after.time,
        )
        tight = reference.integrate(
            raw,
            point.state._asdict(),
            record,
            component.diffusion.current_m2_s,
            start_time_s=point.time,
            end_time_s=after.time,
            refinement=2,
        )
        c = tight["context"]
        oracle = reference.view.ORACLES[raw["model"]["id"]]
        target = tight["state"]
        atol = oracle.flatten(
            c,
            {
                name: np.full(shape, 3e-23 if name.endswith("_C") else 3e-12)
                for name, shape in c["shapes"].items()
            },
        )
        budget = atol + 3e-10 * np.abs(target)
        actual = oracle.flatten(c, after.state._asdict())
        error = float(np.max(np.abs(actual - target) / budget, initial=0))
        uncertainty = float(np.max(np.abs(standard["state"] - target) / budget, initial=0))
        runtime = view.evaluate(
            spec, point.state, point.layout, control(spec, point.time), binding, component, step_s=h
        ).runtime_layout
        endpoint_field = implementation.field_values(
            after.state, control(spec, after.time), runtime, xp=np
        )
        actual_phi = np.r_[
            endpoint_field.potential_V[: runtime.active.size][runtime.active],
            endpoint_field.potential_V[runtime.active.size :][runtime.outside_active],
        ]
        phi_budget = 3e-13 + 3e-10 * np.abs(tight["endpoint_potential_V"])
        same_state_phi = oracle.evaluate(c, actual, after.time)[1]
        phi_error = float(
            np.max(np.abs(actual_phi - tight["endpoint_potential_V"]) / phi_budget, initial=0)
        )
        field_error = float(
            np.max(np.abs(actual_phi - same_state_phi) / phi_budget, initial=0)
        )
        phi_uncertainty = float(
            np.max(
                np.abs(standard["endpoint_potential_V"] - tight["endpoint_potential_V"])
                / phi_budget,
                initial=0,
            )
        )
        first = tissue.array_rk4_step(
            point.state,
            control(spec, point.time),
            runtime,
            h / 2,
            implementation=implementation,
            xp=np,
        )
        second = tissue.array_rk4_step(
            first.proposed_state,
            control(spec, point.time),
            runtime,
            h / 2,
            implementation=implementation,
            xp=np,
        )
        refined = oracle.flatten(c, second.proposed_state._asdict())
        refined_error = float(np.max(np.abs(refined - target) / budget, initial=0))
        refined_field = implementation.field_values(
            second.proposed_state, control(spec, after.time), runtime, xp=np
        )
        refined_phi = np.r_[
            refined_field.potential_V[: runtime.active.size][runtime.active],
            refined_field.potential_V[runtime.active.size :][runtime.outside_active],
        ]
        refined_phi_error = float(
            np.max(np.abs(refined_phi - tight["endpoint_potential_V"]) / phi_budget, initial=0)
        )
        trajectory_potential_errors.append(phi_error)
        evidence(
            "interval-" + kind + "-" + str(at_event) + "-" + str(index),
            dict(
                definition=raw,
                binding=record,
                source_fields=point.state._asdict(),
                current_diffusion_m2_s=component.diffusion.current_m2_s,
                start_time_s=point.time,
                end_time_s=after.time,
                full_interval_s=h,
                state_fields=len(after.state),
                coarse_error_fraction=error,
                half_step_error_fraction=refined_error,
                oracle_uncertainty_fraction=uncertainty,
                trajectory_potential_error_fraction=phi_error,
                half_step_potential_error_fraction=refined_phi_error,
                same_state_field_error_fraction=field_error,
                oracle_potential_uncertainty_fraction=phi_uncertainty,
                stage_status=[status._asdict() for status in result.trial.status],
                held_control=result.admission["held_control"]._asdict(),
                endpoint_control=result.admission["endpoint_control"]._asdict(),
                refinement_scope="two internal half steps; no intermediate public checkpoint",
            ),
            dict(
                actual=actual,
                half_steps=refined,
                oracle=target,
                standard=standard["state"],
                budget=budget,
                error=actual - target,
                half_step_error=refined - target,
                actual_endpoint_phi=actual_phi,
                half_steps_endpoint_phi=refined_phi,
                same_state_oracle_phi=same_state_phi,
                oracle_endpoint_phi=tight["endpoint_potential_V"],
                standard_endpoint_phi=standard["endpoint_potential_V"],
                potential_budget=phi_budget,
            ),
        )
        assert first.valid and second.valid
        assert error <= 1 and refined_error <= 1 and uncertainty <= 0.1
        assert field_error <= 1 and phi_uncertainty <= 0.1
        assert refined_error <= error or max(error, refined_error) <= 0.01
        assert result.binding is binding and result.component is component
        assert after.layout is original_layout
        assert after.step_index == point.step_index + 1
        assert after.event_index == event_index(spec, after.time)
        assert fingerprints(spec, point.state, point.layout, component) == before
        validate_checkpoint(spec, after, times=EventGrid(spec))
        if at_event and index == 0:
            assert after.time == 0.75 * spec.execution.dt
            assert not np.array_equal(
                result.admission["held_control"].membrane,
                result.admission["endpoint_control"].membrane,
            )
        point = after
    if max(trajectory_potential_errors) > 1:
        raise EndpointPotentialAccuracyError(trajectory_potential_errors)


def test_predeclared_finer_passive_source_grid_covers_same_physical_horizon():
    original_spec = case("passive")[0]
    original = original_spec.to_dict()
    coarse_dt = original_spec.execution.dt
    horizon = 2 * coarse_dt
    spec, point, binding, component, implementation = case("passive", source_dt_scale=0.5)
    raw, record = spec.to_dict(), units.binding_record(binding)
    assert spec.execution.dt == coarse_dt / 2
    assert raw["model"] == original["model"]
    assert raw["experiment"] == original["experiment"]
    assert {key: value for key, value in raw["execution"].items() if key != "dt"} == {
        key: value for key, value in original["execution"].items() if key != "dt"
    }
    oracle = reference.view.ORACLES[raw["model"]["id"]]
    standard_fields = tight_fields = point.state._asdict()
    layout = point.layout
    runtime = view.evaluate(
        spec, point.state, layout, control(spec, 0.0), binding, component, step_s=spec.execution.dt
    ).runtime_layout
    intervals = []
    for index, end in enumerate(t for t in EventGrid(spec) if 0 < t <= horizon):
        before = fingerprints(spec, point.state, layout, component)
        result = tissue.advance(spec, point, binding, component, end_time_s=end)
        after = result.checkpoint
        standard = reference.integrate(
            raw,
            standard_fields,
            record,
            component.diffusion.current_m2_s,
            start_time_s=point.time,
            end_time_s=end,
        )
        tight = reference.integrate(
            raw,
            tight_fields,
            record,
            component.diffusion.current_m2_s,
            start_time_s=point.time,
            end_time_s=end,
            refinement=2,
        )
        c, target = tight["context"], tight["state"]
        actual = oracle.flatten(c, after.state._asdict())
        budget = oracle.flatten(
            c,
            {
                name: np.full(shape, 3e-23 if name.endswith("_C") else 3e-12)
                for name, shape in c["shapes"].items()
            },
        ) + 3e-10 * np.abs(target)
        field = implementation.field_values(after.state, control(spec, end), runtime, xp=np)
        actual_phi = np.r_[
            field.potential_V[: runtime.active.size][runtime.active],
            field.potential_V[runtime.active.size :][runtime.outside_active],
        ]
        phi_budget = 3e-13 + 3e-10 * np.abs(tight["endpoint_potential_V"])
        errors = dict(
            state_error_fraction=float(np.max(np.abs(actual - target) / budget, initial=0)),
            trajectory_potential_error_fraction=float(
                np.max(np.abs(actual_phi - tight["endpoint_potential_V"]) / phi_budget, initial=0)
            ),
            oracle_uncertainty_fraction=float(
                np.max(np.abs(standard["state"] - target) / budget, initial=0)
            ),
            oracle_potential_uncertainty_fraction=float(
                np.max(
                    np.abs(standard["endpoint_potential_V"] - tight["endpoint_potential_V"])
                    / phi_budget,
                    initial=0,
                )
            ),
        )
        evidence(
            "fine-source-passive-step-" + str(index),
            dict(
                definition=raw,
                original_definition=original,
                binding=record,
                source_fields=standard_fields,
                tight_source_fields=tight_fields,
                production_source_fields=point.state._asdict(),
                current_diffusion_m2_s=component.diffusion.current_m2_s,
                start_time_s=point.time,
                end_time_s=end,
                original_source_dt_s=coarse_dt,
                source_dt_s=spec.execution.dt,
                compared_physical_horizon_s=horizon,
                errors=errors,
                scope=(
                    "Accepted source-grid refinement of the retained coarse passive recipe; "
                    "chained independent DOP trajectories start at the same original initial state"
                ),
            ),
            dict(
                actual=actual,
                standard=standard["state"],
                oracle=target,
                budget=budget,
                error=actual - target,
                actual_endpoint_phi=actual_phi,
                standard_endpoint_phi=standard["endpoint_potential_V"],
                oracle_endpoint_phi=tight["endpoint_potential_V"],
                potential_budget=phi_budget,
            ),
        )
        assert errors["state_error_fraction"] <= 1
        assert errors["trajectory_potential_error_fraction"] <= 1
        assert errors["oracle_uncertainty_fraction"] <= 0.1
        assert errors["oracle_potential_uncertainty_fraction"] <= 0.1
        assert fingerprints(spec, point.state, layout, component) == before
        assert after.layout is layout
        assert result.binding is binding and result.component is component
        validate_checkpoint(spec, after, times=EventGrid(spec))
        intervals.append(dict(start_time_s=point.time, end_time_s=end, **errors))
        standard_fields = oracle.unpack(c, standard["state"])
        tight_fields = oracle.unpack(c, target)
        point = after
    assert point.time == horizon and len(intervals) == 4
    assert {coarse_dt, horizon} <= {row["end_time_s"] for row in intervals}
    evidence(
        "refined-source-passive",
        dict(
            original_source_dt_s=coarse_dt,
            source_dt_s=spec.execution.dt,
            physical_horizon_s=horizon,
            source_experiment_end_time_s=spec.experiment.end_time,
            original_experiment_preserved=True,
            intervals=intervals,
            distinct_biological_cases=0,
        ),
    )


@pytest.mark.parametrize("kind", KINDS)
def test_restored_JAX_layout_retains_identity_and_matches_host_at_event_and_evolved_step(kind):
    spec, point, binding, component, _ = case(kind, at_event=True)
    restored = replace(
        point,
        state=jax.tree.map(jnp.asarray, point.state),
        layout=jax.tree.map(jnp.asarray, point.layout),
    )
    original_layout = restored.layout

    def restored_fingerprint():
        return fingerprints(
            spec,
            jax.tree.map(np.asarray, restored.state),
            jax.tree.map(np.asarray, restored.layout),
            component,
        )

    for _ in range(2):
        before = restored_fingerprint()
        expected = tissue.advance(spec, point, binding, component)
        actual = tissue.advance(spec, restored, binding, component)
        exact_tree(actual.checkpoint.state, expected.checkpoint.state)
        assert actual.checkpoint.layout is original_layout
        assert actual.binding is binding and actual.component is component
        assert restored_fingerprint() == before
        validate_checkpoint(spec, actual.checkpoint, times=EventGrid(spec))
        point, restored = expected.checkpoint, actual.checkpoint


@pytest.mark.parametrize("kind", KINDS)
def test_unchanged_P_matches_every_field_of_established_RK4_on_initial_and_evolved_states(kind):
    spec, point, binding, component, implementation = case(kind, changed=False)
    for _ in range(2):
        grid = EventGrid(spec)
        end = grid[point.step_index + 1]
        expected = rk4_step(
            lambda state, held, p, active: implementation.rhs(state, held, p, active, xp=np),
            point.state,
            end - point.time,
            control(spec, point.time),
            point.layout,
            point.layout.active,
        )
        result = tissue.advance(spec, point, binding, component)
        exact_tree(result.checkpoint.state, expected)
        assert result.checkpoint.layout is point.layout
        point = result.checkpoint


def test_component_and_binding_are_unchanged_without_draw_finalize_or_clock_synchronization(
    monkeypatch,
):
    spec, point, binding, component, _ = case("fuel")
    component = replace(component, time_s=0.012, loop_calls=6)
    before = fingerprints(spec, point.state, point.layout, component)

    def forbidden(*args, **kwargs):
        pytest.fail("A tissue-only step performed a component update")

    with monkeypatch.context() as guard:
        for module, name in (
            (streams, "draw"),
            (perturb, "sample_native"),
            (perturb, "sample_stable"),
            (perturb, "finalize_scheduled"),
            (component_step, "advance"),
        ):
            guard.setattr(module, name, forbidden)
        result = tissue.advance(spec, point, binding, component)
    assert result.binding is binding and result.component is component
    assert fingerprints(spec, point.state, point.layout, component) == before
    assert result.checkpoint.time > point.time and component.time_s == 0.012


@pytest.mark.parametrize("fault", ["time", "step_index", "event_index", "skip", "nonfinite_end"])
def test_exact_source_clock_and_next_event_boundary_are_required(fault):
    spec, point, binding, component, _ = case(at_event=True)
    kwargs = {}
    if fault == "time":
        point = replace(point, time=point.time + spec.execution.dt / 10)
    elif fault == "step_index":
        point = replace(point, step_index=True)
    elif fault == "event_index":
        point = replace(point, event_index=17)
    elif fault == "skip":
        kwargs["end_time_s"] = spec.execution.dt
    else:
        kwargs["end_time_s"] = np.nan
    with pytest.raises(tissue.TissueStepRejected) as caught:
        tissue.advance(spec, point, binding, component, **kwargs)
    assert caught.value.trial is None
    assert caught.value.source_checkpoint is point
    assert caught.value.binding is binding and caught.value.component is component


def test_terminal_checkpoint_has_no_hidden_extra_step():
    raw = definition("passive")
    raw["experiment"]["end_time"] = raw["execution"]["dt"]
    raw["experiment"]["observation_times"] = [0.0, raw["execution"]["dt"]]
    spec = parse_spec(raw)
    binding = units.bind_tissue(spec, **arguments(spec))
    component = component_state(binding)
    implementation = view.passive
    state, p = implementation.initial_values(spec)
    point = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    final = tissue.advance(spec, point, binding, component).checkpoint
    with pytest.raises(tissue.TissueStepRejected, match="no next"):
        tissue.advance(spec, final, binding, component)


@pytest.mark.parametrize("direction", ["positive_to_zero", "zero_to_positive"])
def test_route_support_changes_refuse_before_RK_trial(direction):
    raw = definition("passive")
    if direction == "zero_to_positive":
        raw["model"]["membranes"][0]["permeability_m_per_s"]["Na"] = 0.0
    spec = parse_spec(raw)
    binding = units.bind_tissue(spec, **arguments(spec))
    component = component_state(binding)
    diffusion = component.diffusion.current_m2_s.copy()
    j = binding.component.membrane_ids.index(spec.model.membranes[0].id)
    i = binding.component.ion_ids.index("Na")
    diffusion[i, j] = 0.0 if direction == "positive_to_zero" else 1e-18
    component = replace(component, diffusion=component.diffusion._replace(current_m2_s=diffusion))
    state, p = view.passive.initial_values(spec)
    point = Checkpoint(state, p, 0.0, 0, event_index(spec, 0.0))
    with pytest.raises(tissue.TissueStepRejected, match="support") as caught:
        tissue.advance(spec, point, binding, component)
    assert caught.value.stage == "route_support" and caught.value.trial is None


@pytest.mark.parametrize("failure", ["domain", "linear_solve"])
def test_rejected_RK_stage_retains_raw_trial_and_all_accepted_inputs(failure, monkeypatch):
    spec, point, binding, component, implementation = case()
    before = fingerprints(spec, point.state, point.layout, component)
    original_domain = implementation.domain_valid
    original_field = implementation.field_values

    def domain(state, p, active, *, xp):
        if failure == "domain" and np.any(np.asarray(state.amount_increment) != 0):
            return np.asarray(False)
        return original_domain(state, p, active, xp=xp)

    def field(state, held, p, *, xp):
        if failure == "linear_solve" and np.any(np.asarray(state.amount_increment) != 0):
            raise np.linalg.LinAlgError("prescribed field failure")
        return original_field(state, held, p, xp=xp)

    with monkeypatch.context() as guard:
        guard.setattr(implementation, "domain_valid", domain)
        guard.setattr(implementation, "field_values", field)
        with pytest.raises(tissue.TissueStepRejected) as caught:
            tissue.advance(spec, point, binding, component)
    error = caught.value
    assert error.stage == "rk4_trial" and error.trial is not None
    assert int(error.trial.first_invalid_stage) == 1
    assert np.any(error.trial.stages[1].amount_increment != 0)
    assert fingerprints(spec, point.state, point.layout, component) == before
    evidence(
        "rejected-" + failure,
        dict(
            stage=error.stage,
            first_invalid=1,
            source_time_s=point.time,
            proposed_time_s=error.end_time_s,
            status=[row._asdict() for row in error.trial.status],
        ),
        {"raw_stage2__" + key: value for key, value in error.trial.stages[1]._asdict().items()},
    )


def test_pure_kernel_does_not_apply_exact_energy_checks_to_RK_intermediate_trials(monkeypatch):
    spec, point, binding, component, implementation = case()
    held = control(spec, 0.0)
    prepared = view.evaluate(
        spec, point.state, point.layout, held, binding, component, step_s=spec.execution.dt
    )

    def forbidden(*args, **kwargs):
        pytest.fail("An RK trial ran host integrated conservation admission")

    with monkeypatch.context() as guard:
        guard.setattr(implementation, "check_values", forbidden)
        guard.setattr(view, "evaluate", forbidden)
        trial = tissue.array_rk4_step(
            point.state,
            held,
            prepared.runtime_layout,
            spec.execution.dt,
            implementation=implementation,
            xp=np,
        )
    assert trial.valid


def test_array_kernel_numpy_and_cpu_jax_eager_correspondence():
    spec, point, binding, component, implementation = case(changed=False)
    held = control(spec, 0.0)
    runtime = view.evaluate(
        spec, point.state, point.layout, held, binding, component, step_s=spec.execution.dt
    ).runtime_layout
    expected = tissue.array_rk4_step(
        point.state, held, runtime, spec.execution.dt, implementation=implementation, xp=np
    )
    actual = tissue.array_rk4_step(
        jax.tree.map(jnp.asarray, point.state),
        jax.tree.map(jnp.asarray, held),
        jax.tree.map(jnp.asarray, runtime),
        spec.execution.dt,
        implementation=implementation,
        xp=jnp,
    )
    assert actual.valid and expected.valid
    for a, b in zip(actual.proposed_state, expected.proposed_state, strict=True):
        np.testing.assert_allclose(a, b, rtol=3e-10, atol=3e-12)


def test_accepted_result_and_trial_arrays_are_immutable():
    spec, point, binding, component, _ = case()
    result = tissue.advance(spec, point, binding, component)
    for value in jax.tree.leaves(result.trial):
        with pytest.raises(ValueError):
            value.setflags(write=True)
    with pytest.raises(TypeError):
        result.admission["step_s"] = 0.0
