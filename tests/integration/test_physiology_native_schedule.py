"""Native event labels with fixed-duration charged loops and complete restart."""

import json
from dataclasses import replace
from functools import lru_cache

import numpy as np
import pytest

from cells import physiology_protein_loop_io as persistence
from cells.core import physiology_native_calendar as calendars
from cells.core import physiology_permeability_schedule as schedule
from cells.core import physiology_perturbation_phases as phases
from cells.core import physiology_protein_loop as loop
from cells.core import physiology_random_streams as streams
from cells.core.errors import NumericalError
from cells.core.grid import EventGrid
from cells.core.specs import digest
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_permeability_schedule import CASES, qualify_carried
from tests.integration.test_physiology_permeability_schedule import inputs as nominal_inputs
from tests.integration.test_physiology_protein_loop import budget
from tests.integration.test_physiology_protein_transition import plain_component
from tests.unit.test_physiology_permeability_view import exact_tree
from tests.unit.test_physiology_tissue_step import evidence
from validation.perturbations import permeability_schedule_native as native
from validation.perturbations import physiology_calendar_native as source_calendar


@lru_cache(maxsize=24)
def inputs(kind="passive", law="native", profile="normal", count=3):
    spec, original, previous = nominal_inputs(kind, law, profile)
    component, binding = original.initial_component, original.origin.binding
    calendar = calendars.bind(
        phase=component.controls.phase,
        step_count=count,
        dt_s=component.controls.dt_s,
        sample_stride=1,
        provenance="Complete original phase for native event-label comparison",
    )
    plan = schedule.bind(
        spec,
        binding,
        component,
        changes=previous.changes,
        pulses=previous.pulses,
        native_calendar=calendar,
    )
    point = loop.initialise(
        spec,
        original.origin.seed,
        binding,
        original.origin.charge_reference,
        component,
        protein_species_id=original.origin.protein_species_id,
        valence=original.origin.valence,
        standard_concentration_mol_m3=1.0,
        schedule=plan,
    )
    return spec, point, plan


@pytest.mark.parametrize("kind", ("passive", "ionic", "calcium", "fuel"))
def test_native_calendar_buffer_arithmetic_matches_actual_source_calls(kind, monkeypatch):
    spec, point, plan = inputs(kind)
    component, binding = point.initial_component, point.origin.binding
    saved = schedule.record(plan)
    plain = plain_component(component)
    labels = source_calendar.evaluate(saved["native_calendar"], solver="normal")
    nominal = schedule.bind(spec, binding, component, changes=plan.changes, pulses=plan.pulses)

    def forbidden(*args, **kwargs):
        pytest.fail("Calendar staging drew random values")

    monkeypatch.setattr(streams, "draw", forbidden)
    cases = []
    for index, label in enumerate(labels["event_label_s"]):
        staged = schedule.stage(plan, component, component, binding, index)
        prepared = phases.prepare(staged, binding.component)
        wanted = native.evaluate(
            saved, loop.held.units.binding_record(binding), plain, plain, index
        )
        assert schedule.sample_time_s(plan, index) == label
        for name, value in prepared.held_state.diffusion._asdict().items():
            np.testing.assert_array_equal(value, wanted[name])
        assert staged.stream == component.stream and staged.time_s == component.time_s
        assert staged.loop_calls == component.loop_calls
        exact_tree(staged.protein, component.protein)
        if index > 0:
            other = schedule.stage(nominal, component, component, binding, index)
            assert not np.array_equal(
                other.diffusion.scheduled_m2_s, staged.diffusion.scheduled_m2_s
            )
        cases.append(
            dict(
                loop_index=index,
                event_label_s=label,
                actual=prepared.held_state.diffusion._asdict(),
                expected=wanted,
            )
        )
    evidence(
        "native-clock-buffer-" + kind,
        dict(
            plan=saved,
            binding=loop.held.units.binding_record(binding),
            initial=plain,
            cases=cases,
            native_calendar=labels,
            scope="Pinned calendar and membrane sites; no native ionic loop",
        ),
    )


@pytest.mark.parametrize(
    "defect", ("phase", "duration", "empty", "origin", "horizon", "last_change", "seal")
)
def test_native_calendar_binding_preserves_complete_phase_association(defect):
    spec, point, plan = inputs()
    component, binding = point.initial_component, point.origin.binding
    changes, origin = plan.changes, 0
    calendar = plan.native_calendar
    raw = dict(
        phase=calendar.phase,
        step_count=calendar.step_count,
        dt_s=calendar.dt_s,
        sample_stride=1,
        provenance=calendar.provenance,
    )
    if defect == "phase":
        raw["phase"] = "INIT"
    elif defect == "duration":
        raw["dt_s"] *= 2
    elif defect == "empty":
        raw["step_count"] = 0
    elif defect == "origin":
        origin = 1
    elif defect == "horizon":
        raw["step_count"] = int(EventGrid(spec).end / calendar.dt_s) + 1
    elif defect == "last_change":
        changes = (
            *changes,
            schedule.BufferChange(
                3, component.diffusion.scheduled_m2_s, "Invalid post-completion intervention"
            ),
        )
    calendar = calendars.bind(**raw)
    if defect == "seal":
        calendar = replace(calendar, identity="0" * 64)
    with pytest.raises(ValueError):
        schedule.bind(
            spec,
            binding,
            component,
            origin_loop_index=origin,
            changes=changes,
            pulses=plan.pulses,
            native_calendar=calendar,
        )


@pytest.mark.parametrize("kind,law", CASES)
def test_coupled_native_event_labels_restart_and_independent_trajectories(
    tmp_path, kind, law, monkeypatch
):
    prepared = inputs(kind, law)
    spec, origin, plan = prepared
    labels = source_calendar.evaluate(calendars.record(plan.native_calendar), solver="normal")
    terminal = qualify_carried(
        tmp_path,
        kind,
        law,
        prepared=prepared,
        event_labels=labels["event_label_s"],
        prefix="native-clock-loop",
    )
    assert terminal.loop_index == plan.native_calendar.step_count
    assert terminal.time == plan.native_calendar.step_count * plan.physiological_dt_s
    # The component's sequential floating clock is independent of event labels.
    component_time = origin.component.time_s
    for _ in range(3):
        component_time += plan.physiological_dt_s
    assert terminal.component.time_s == component_time
    path = persistence.write_protein_loop_checkpoint(tmp_path / "terminal", spec, terminal)
    resumed = persistence.load_protein_loop_checkpoint(path).checkpoint
    assert resumed.identity == terminal.identity
    assert calendars.record(resumed.schedule.native_calendar) == calendars.record(
        plan.native_calendar
    )

    def forbidden(*args, **kwargs):
        pytest.fail("An exhausted native phase drew randomness")

    monkeypatch.setattr(streams, "draw", forbidden)
    with pytest.raises(loop.ProteinLoopRejected) as caught:
        loop.propose(spec, resumed)
    assert caught.value.stage == "preparation"
    assert caught.value.source is resumed
    assert not caught.value.intervals
    evidence(
        "native-clock-terminal-" + kind + "-" + law,
        dict(
            calendar=calendars.record(plan.native_calendar),
            checkpoint=resumed.identity,
            time_s=resumed.time,
            failure_stage=caught.value.stage,
            failure=str(caught.value),
            accepted_history_unchanged=True,
        ),
    )


@pytest.mark.parametrize("profile", ("INIT", "fast", "dynamic_off", "protein_off", "zero_level"))
def test_native_calendar_retains_event_and_component_guards(profile):
    spec, point, plan = inputs(profile=profile)
    proposal = loop.propose(spec, point)
    receipt = loop.accept(spec, point, proposal, budget(proposal))
    active = perturb.dynamic_active(point.component.controls)
    assert receipt.checkpoint.component.stream.next_tick == point.component.stream.next_tick + int(
        active
    )
    assert proposal.permeability_staging["events_applied"] == (profile != "INIT")
    assert proposal.permeability_staging["sampled_time_s"] == 0.0
    if profile == "INIT":
        exact_tree(receipt.checkpoint.component.diffusion, point.component.diffusion)
    assert receipt.checkpoint.time == plan.physiological_dt_s


@pytest.mark.parametrize("defect", ("missing", "count", "phase", "nominal_downgrade"))
def test_saved_calendar_cannot_be_removed_rebased_or_relabelled(tmp_path, defect):
    spec, point, plan = inputs()
    proposal = loop.propose(spec, point)
    point = loop.accept(spec, point, proposal, budget(proposal)).checkpoint
    path = persistence.write_protein_loop_checkpoint(tmp_path / "source", spec, point)
    saved = json.loads((path / "schedule.json").read_text())
    if defect == "missing":
        saved.pop("native_calendar")
    elif defect == "nominal_downgrade":
        saved = schedule.record(
            schedule.bind(
                spec,
                point.origin.binding,
                point.initial_component,
                changes=plan.changes,
                pulses=plan.pulses,
            )
        )
    else:
        raw = dict(
            phase="INIT" if defect == "phase" else "SIM",
            step_count=4 if defect == "count" else 3,
            dt_s=plan.physiological_dt_s,
            provenance=plan.native_calendar.provenance,
        )
        saved["native_calendar"] = calendars.record(calendars.bind(**raw))
        saved["identity"] = digest({k: v for k, v in saved.items() if k != "identity"})
    (path / "schedule.json").write_text(json.dumps(saved))
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["files"]["schedule.json"] = persistence._sha(path / "schedule.json")
    manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, NumericalError)):
        persistence.load_protein_loop_checkpoint(path)


def test_equal_first_label_does_not_allow_cross_calendar_proposal_reuse():
    spec, point, _ = inputs(count=3)
    other_spec, other, _ = inputs(count=4)
    assert spec.to_dict() == other_spec.to_dict()
    exact_tree(point.state, other.state)
    proposal = loop.propose(spec, point)
    with pytest.raises(loop.ProteinLoopRejected):
        loop.accept(spec, other, proposal, budget(proposal))
