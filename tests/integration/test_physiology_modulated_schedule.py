"""Time-modulated membrane events, fixed-duration coupled loops and restart."""

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
from cells.processes import betse_time_modulation as modulation
from tests.integration.test_physiology_permeability_schedule import CASES, qualify_carried
from tests.integration.test_physiology_permeability_schedule import inputs as nominal_inputs
from tests.integration.test_physiology_protein_loop import budget
from tests.integration.test_physiology_protein_transition import plain_component
from tests.unit.test_physiology_permeability_view import exact_tree
from tests.unit.test_physiology_tissue_step import evidence
from validation.perturbations import permeability_schedule_native as native
from validation.perturbations import physiology_calendar_native as source_calendar


@lru_cache(maxsize=40)
def inputs(kind="passive", law="native", profile="normal", modulator="periodic", native_clock=True):
    spec, original, previous = nominal_inputs(kind, law, profile)
    component, binding = original.initial_component, original.origin.binding
    dt = component.controls.dt_s
    calendar = (
        None
        if not native_clock
        else calendars.bind(
            phase=component.controls.phase,
            step_count=3,
            dt_s=dt,
            provenance="Complete original phase for modulated-event comparison",
        )
    )
    if modulator == "periodic":
        program = modulation.periodic_program(
            frequency_Hz=0.17 / dt,
            phase_rad=0.2,
            provenance="Manufactured variation over the short numerical comparison",
        )
    elif native_clock:
        program = modulation.sweep_program(
            start_Hz=0.05 / dt,
            stop_Hz=0.35 / dt,
            original_duration_s=3 * dt,
            provenance="Original three-call source sweep",
        )
    else:
        program = modulation.sweep_program(
            start_Hz=0.05 / dt,
            slope_Hz_s=0.1 / dt**2,
            provenance="Explicit sweep coefficient on the nominal Cells clock",
        )
    pulse = replace(previous.pulses[0], time_modulator=program, dynamic_scale=0.85)
    plan = schedule.bind(
        spec,
        binding,
        component,
        changes=previous.changes,
        pulses=(pulse,),
        native_calendar=calendar,
    )
    point = initialize(spec, original, plan)
    return spec, point, plan


def initialize(spec, original, plan):
    return loop.initialise(
        spec,
        original.origin.seed,
        original.origin.binding,
        original.origin.charge_reference,
        original.initial_component,
        protein_species_id=original.origin.protein_species_id,
        valence=original.origin.valence,
        standard_concentration_mol_m3=1.0,
        schedule=plan,
    )


@pytest.mark.parametrize("kind", ("passive", "ionic", "calcium", "fuel"))
@pytest.mark.parametrize("modulator", ("periodic", "sweep"))
@pytest.mark.parametrize("native_clock", (False, True))
def test_modulated_buffer_arithmetic_and_call_ownership(kind, modulator, native_clock, monkeypatch):
    spec, point, plan = inputs(kind, modulator=modulator, native_clock=native_clock)
    component, binding = point.initial_component, point.origin.binding
    saved, plain = schedule.record(plan), plain_component(component)
    assert saved["kind"] == schedule.MODULATED_KIND
    assert schedule.restore(saved, spec, binding, component, 0).identity == plan.identity

    def forbidden(*args, **kwargs):
        pytest.fail("Time-factor staging drew randomness")

    monkeypatch.setattr(streams, "draw", forbidden)
    cases = []
    for index in range(3):
        staged = schedule.stage(plan, component, component, binding, index)
        actual = phases.prepare(staged, binding.component).held_state.diffusion
        wanted = native.evaluate(
            saved, loop.held.units.binding_record(binding), plain, plain, index
        )
        for name, value in actual._asdict().items():
            np.testing.assert_array_equal(value, wanted[name])
        exact_tree(staged.protein, component.protein)
        assert staged.stream == component.stream and staged.time_s == component.time_s
        assert staged.loop_calls == component.loop_calls
        cases.append(dict(loop_index=index, actual=actual._asdict(), expected=wanted))
    clock = "native" if native_clock else "nominal"
    evidence(
        "modulated-buffer-" + kind + "-" + modulator + "-" + clock,
        dict(
            plan=saved,
            binding=loop.held.units.binding_record(binding),
            initial=plain,
            cases=cases,
            scope="Captured time-modulator/calendar/targeted-buffer sites only",
        ),
    )


@pytest.mark.parametrize("defect", ("identity", "resolved_slope", "duration", "kind", "callable"))
def test_modulator_binding_refuses_unassociated_programs(defect):
    spec, point, plan = inputs(modulator="sweep")
    original = plan.pulses[0].time_modulator
    if defect == "identity":
        program = replace(original, identity="0" * 64)
    elif defect == "resolved_slope":
        program = replace(original, slope_Hz_s=original.slope_Hz_s * 2)
        program = replace(program, identity=modulation.record(program)["identity"])
    elif defect == "duration":
        program = modulation.sweep_program(
            start_Hz=original.frequency_Hz,
            stop_Hz=original.requested_stop_Hz,
            original_duration_s=4 * plan.physiological_dt_s,
            provenance=original.provenance,
        )
    elif defect == "kind":
        program = replace(original, kind="arbitrary_callback")
    else:
        def program(time):
            return time
    with pytest.raises(ValueError):
        schedule.bind(
            spec,
            point.origin.binding,
            point.initial_component,
            changes=plan.changes,
            pulses=(replace(plan.pulses[0], time_modulator=program),),
            native_calendar=plan.native_calendar,
        )


def test_automatic_slope_uses_requested_native_duration_before_count_truncation():
    spec, point, plan = inputs(modulator="sweep")
    dt = plan.physiological_dt_s
    calendar = calendars.from_duration(
        phase="SIM",
        requested_duration_s=3.3 * dt,
        dt_s=dt,
        provenance="Source requested duration differs from the truncated phase horizon",
    )
    assert calendar.step_count == 3
    old = plan.pulses[0].time_modulator
    program = modulation.sweep_program(
        start_Hz=old.frequency_Hz,
        stop_Hz=old.requested_stop_Hz,
        original_duration_s=calendar.requested_duration_s,
        provenance=old.provenance,
    )
    pulse = replace(plan.pulses[0], time_modulator=program)
    good = schedule.bind(
        spec,
        point.origin.binding,
        point.initial_component,
        changes=plan.changes,
        pulses=(pulse,),
        native_calendar=calendar,
    )
    assert good.pulses[0].time_modulator.original_duration_s != calendar.step_count * dt
    with pytest.raises(ValueError, match="original SIM phase"):
        schedule.bind(
            spec,
            point.origin.binding,
            point.initial_component,
            changes=plan.changes,
            pulses=plan.pulses,
            native_calendar=calendar,
        )


@pytest.mark.parametrize("profile", ("SIM", "INIT"))
def test_nominal_automatic_slope_binds_original_phase_and_setup_guard(profile):
    spec, point, previous = nominal_inputs(profile="normal" if profile == "SIM" else "INIT")
    duration = EventGrid(spec).end
    program = modulation.sweep_program(
        start_Hz=0.0,
        stop_Hz=1.0,
        original_duration_s=duration,
        provenance="Original nominal phase duration",
    )
    pulse = replace(previous.pulses[0], time_modulator=program)
    if profile == "INIT":
        with pytest.raises(ValueError, match="original SIM phase"):
            schedule.bind(spec, point.origin.binding, point.initial_component, pulses=(pulse,))
        return
    plan = schedule.bind(spec, point.origin.binding, point.initial_component, pulses=(pulse,))
    assert plan.pulses[0].time_modulator.original_duration_s == duration
    wrong = modulation.sweep_program(
        start_Hz=0.0,
        stop_Hz=1.0,
        original_duration_s=duration + previous.physiological_dt_s,
        provenance=program.provenance,
    )
    with pytest.raises(ValueError, match="original SIM phase"):
        schedule.bind(
            spec,
            point.origin.binding,
            point.initial_component,
            pulses=(replace(pulse, time_modulator=wrong),),
        )


@pytest.mark.parametrize("profile", ("INIT", "fast", "dynamic_off", "protein_off", "zero_level"))
def test_modulated_component_preserves_phase_and_random_guards(profile, monkeypatch):
    spec, point, _ = inputs(profile=profile)
    if profile == "INIT":

        def forbidden(*args, **kwargs):
            pytest.fail("INIT sampled a disabled intervention factor")

        monkeypatch.setattr(modulation, "evaluate", forbidden)
    proposal = loop.propose(spec, point)
    result = loop.accept(spec, point, proposal, budget(proposal)).checkpoint
    assert result.component.stream.next_tick == point.component.stream.next_tick + int(
        perturb.dynamic_active(point.component.controls)
    )
    if profile == "INIT":
        exact_tree(result.component.diffusion, point.component.diffusion)


@pytest.mark.parametrize("kind,law", CASES)
def test_coupled_modulated_events_restart_and_independent_carried_trajectories(tmp_path, kind, law):
    modulator = "sweep" if kind in ("ionic", "fuel") or law == "stable" else "periodic"
    use_native = kind not in ("passive", "fuel") or law == "stable"
    prepared = inputs(kind, law, modulator=modulator, native_clock=use_native)
    spec, _, plan = prepared
    labels = (
        None
        if not use_native
        else source_calendar.evaluate(calendars.record(plan.native_calendar), solver="normal")[
            "event_label_s"
        ]
    )
    point = qualify_carried(
        tmp_path, kind, law, prepared=prepared, event_labels=labels, prefix="modulated-loop"
    )
    path = persistence.write_protein_loop_checkpoint(tmp_path / "complete", spec, point)
    restored = persistence.load_protein_loop_checkpoint(path).checkpoint
    assert schedule.record(restored.schedule) == schedule.record(plan)
    assert restored.identity == point.identity
    if use_native:
        with pytest.raises(loop.ProteinLoopRejected) as caught:
            loop.propose(spec, restored)
        assert caught.value.stage == "preparation" and not caught.value.intervals


@pytest.mark.parametrize(
    "defect", ("missing", "coefficient_resealed", "duration", "kind_downgrade")
)
def test_saved_modulation_cannot_change_future_program(tmp_path, defect):
    spec, point, plan = inputs()
    proposal = loop.propose(spec, point)
    point = loop.accept(spec, point, proposal, budget(proposal)).checkpoint
    path = persistence.write_protein_loop_checkpoint(tmp_path / "saved", spec, point)
    saved = json.loads((path / "schedule.json").read_text())
    if defect == "missing":
        saved["pulses"][0].pop("time_modulator")
    elif defect == "coefficient_resealed":
        original = plan.pulses[0].time_modulator
        changed = modulation.periodic_program(
            frequency_Hz=original.frequency_Hz * 2,
            phase_rad=original.phase_rad,
            provenance=original.provenance,
        )
        saved["pulses"][0]["time_modulator"] = modulation.record(changed)
        saved["identity"] = digest({k: v for k, v in saved.items() if k != "identity"})
    elif defect == "duration":
        saved["pulses"][0]["time_modulator"]["original_duration_s"] = 1.0
    else:
        saved["kind"] = schedule.NATIVE_KIND
    (path / "schedule.json").write_text(json.dumps(saved))
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["files"]["schedule.json"] = persistence._sha(path / "schedule.json")
    manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, NumericalError)):
        persistence.load_protein_loop_checkpoint(path)


def test_late_nonfinite_modulator_retains_accepted_state_and_rng(tmp_path, monkeypatch):
    spec, source, template = inputs()
    program = modulation.periodic_program(
        frequency_Hz=1e308,
        phase_rad=np.finfo(float).max,
        provenance="Deliberate future source-arithmetic overflow; no phase-accuracy claim",
    )
    plan = schedule.bind(
        spec,
        source.origin.binding,
        source.initial_component,
        changes=template.changes,
        pulses=(replace(template.pulses[0], time_modulator=program),),
        native_calendar=template.native_calendar,
    )
    point = initialize(spec, source, plan)
    proposal = loop.propose(spec, point)
    point = loop.accept(spec, point, proposal, budget(proposal)).checkpoint
    path = persistence.write_protein_loop_checkpoint(tmp_path / "before-failure", spec, point)
    resumed = persistence.load_protein_loop_checkpoint(path).checkpoint

    def forbidden(*args, **kwargs):
        pytest.fail("Rejected modulator advanced randomness")

    monkeypatch.setattr(streams, "draw", forbidden)
    for current in (point, resumed):
        with pytest.raises(loop.ProteinLoopRejected) as caught:
            loop.propose(spec, current)
        assert caught.value.stage == "preparation" and not caught.value.intervals
        assert caught.value.source is current and current.identity == point.identity
        assert "Nonfinite time modulator" in str(caught.value)
    evidence(
        "modulated-late-failure",
        dict(
            schedule=schedule.record(plan),
            accepted_checkpoint=point.identity,
            retained_checkpoint=str(path),
            failure_stage="preparation",
            random_draws_during_refusal=0,
            scope="Numerical refusal case, not a qualified large-phase trajectory",
        ),
    )
