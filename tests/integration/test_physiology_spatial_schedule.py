"""Geometry-bound spatial pulses, exact source writes and carried charged loops."""

import json
from dataclasses import asdict, replace
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
from cells.core.specs import digest
from cells.processes import betse_perturbations as perturb
from cells.processes import betse_spatial_modulation as spatial
from tests.integration.test_physiology_modulated_schedule import initialize
from tests.integration.test_physiology_modulated_schedule import inputs as time_inputs
from tests.integration.test_physiology_permeability_schedule import CASES, qualify_carried
from tests.integration.test_physiology_protein_loop import budget
from tests.integration.test_physiology_protein_transition import plain_component
from tests.unit.test_physiology_permeability_view import exact_tree
from tests.unit.test_physiology_tissue_step import evidence
from validation.perturbations import permeability_schedule_native as native
from validation.perturbations import physiology_calendar_native as source_calendar


def spatial_program(binding, kind):
    owners = binding.component
    assert len(owners.cell_ids) == 2 and len(owners.membrane_ids) == 4
    length = 2.0**-20
    return spatial.bind(
        kind=kind,
        target_domain="membranes",
        target_ids=owners.membrane_ids,
        cell_ids=owners.cell_ids,
        membrane_ids=owners.membrane_ids,
        cell_centres_m=np.array([[-1, 1], [2, -1]], dtype=np.float64) * length,
        membrane_midpoints_m=np.array([[-2, 0], [0, 2], [1, -2], [3, 1]], dtype=np.float64)
        * length,
        centre_m=[0.5 * length, 0.0],
        x_offset=0.25 * length if kind == "gradient_r" else 0.13,
        exponent=None if kind == "gradient_r" else 2.0,
        slope=0.7,
        z_offset=0.2,
        provenance=(
            "Manufactured SI stimulation coordinates on the named fixed graph; no mesh inference"
        ),
    )


@lru_cache(maxsize=64)
def inputs(
    kind="passive",
    law="native",
    profile="normal",
    gradient="gradient_x",
    native_clock=True,
    temporal=False,
):
    temporal_law = "sweep" if gradient == "gradient_r" else "periodic"
    spec, original, previous = time_inputs(kind, law, profile, temporal_law, native_clock)
    program = spatial_program(original.origin.binding, gradient)
    row = replace(
        previous.pulses[0],
        spatial_scalar=None,
        spatial_modulator=program,
        time_modulator=previous.pulses[0].time_modulator if temporal else None,
    )
    plan = schedule.bind(
        spec,
        original.origin.binding,
        original.initial_component,
        changes=previous.changes,
        pulses=(row,),
        native_calendar=previous.native_calendar,
    )
    return spec, initialize(spec, original, plan), plan


@pytest.mark.parametrize("kind", ("passive", "ionic", "calcium", "fuel"))
@pytest.mark.parametrize("gradient", ("gradient_x", "gradient_y", "gradient_r"))
@pytest.mark.parametrize("native_clock", (False, True))
@pytest.mark.parametrize("temporal", (False, True))
def test_spatial_buffer_source_arithmetic_and_no_runtime_geometry_or_random_draw(
    kind, gradient, native_clock, temporal, monkeypatch
):
    spec, point, plan = inputs(
        kind, gradient=gradient, native_clock=native_clock, temporal=temporal
    )
    component, binding = point.initial_component, point.origin.binding
    saved, plain = schedule.record(plan), plain_component(component)
    assert saved["kind"] == schedule.SPATIAL_KIND
    assert schedule.restore(saved, spec, binding, component, 0).identity == plan.identity
    wanted_factors = spatial.evaluate(plan.pulses[0].spatial_modulator, xp=np).factor
    np.testing.assert_array_equal(plan.pulses[0].spatial_scalar, wanted_factors)

    def forbidden(*args, **kwargs):
        pytest.fail("Staging changed geometry or sampled randomness")

    monkeypatch.setattr(streams, "draw", forbidden)
    monkeypatch.setattr(spatial, "evaluate", forbidden)
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
    suffix = ("native" if native_clock else "nominal") + ("-time" if temporal else "-static")
    evidence(
        "spatial-buffer-" + kind + "-" + gradient + "-" + suffix,
        dict(
            plan=saved,
            binding=loop.held.units.binding_record(binding),
            initial=plain,
            cases=cases,
            scope=(
                "Captured spatial factor, optional time-factor composition and targeted-buffer "
                "sites; not native configuration import"
            ),
        ),
    )


@pytest.mark.parametrize(
    "defect",
    (
        "identity",
        "cells",
        "membranes",
        "targets",
        "pulse_order",
        "factors",
        "fractional_power",
        "flat_geometry",
    ),
)
def test_spatial_binding_rejects_unassociated_or_nonfinite_maps(defect):
    spec, point, plan = inputs()
    row = plan.pulses[0]
    program = row.spatial_modulator
    if defect == "identity":
        program = replace(program, identity="0" * 64)
    else:
        raw = asdict(program)
        raw.pop("identity")
        if defect == "cells":
            raw["cell_ids"] = ("unknown", *program.cell_ids[1:])
        elif defect == "membranes":
            raw["membrane_ids"] = tuple(reversed(program.membrane_ids))
        elif defect == "targets":
            raw["target_ids"] = tuple(reversed(program.target_ids))
        elif defect == "fractional_power":
            raw.update(x_offset=-1.0, exponent=0.5)
        elif defect == "flat_geometry":
            raw["membrane_midpoints_m"] = ((0.0, 0.0),) * len(program.membrane_ids)
        program = spatial.bind(**raw)
    row = replace(row, spatial_modulator=program, spatial_scalar=None)
    if defect == "pulse_order":
        row = replace(row, membrane_ids=tuple(reversed(row.membrane_ids)))
    elif defect == "factors":
        row = replace(
            row, spatial_scalar=tuple(value * 2 for value in plan.pulses[0].spatial_scalar)
        )
    with pytest.raises(ValueError):
        schedule.bind(
            spec,
            point.origin.binding,
            point.initial_component,
            pulses=(row,),
            native_calendar=plan.native_calendar,
        )


def test_partial_radial_native_assignment_failure_and_cells_refusal_are_retained():
    spec, point, plan = inputs(gradient="gradient_r")
    row = plan.pulses[0]
    parameters = asdict(row.spatial_modulator)
    parameters.pop("identity")
    parameters["target_ids"] = row.membrane_ids[:1]
    partial = spatial.bind(**parameters)
    bad_row = replace(
        row, membrane_ids=row.membrane_ids[:1], spatial_modulator=partial, spatial_scalar=None
    )
    with pytest.raises(ValueError, match="complete ordered"):
        schedule.bind(spec, point.origin.binding, point.initial_component, pulses=(bad_row,))
    raw = schedule.record(plan)
    raw["pulses"][0].update(
        membrane_ids=list(bad_row.membrane_ids), spatial_modulator=spatial.record(partial)
    )
    plain = plain_component(point.initial_component)
    with pytest.raises(ValueError, match="shape mismatch"):
        native.evaluate(raw, loop.held.units.binding_record(point.origin.binding), plain, plain, 0)
    evidence(
        "spatial-partial-source-failure",
        dict(
            plan=raw,
            source_failure="ValueError: shape mismatch",
            cells_refusal="complete ordered bound membrane targets",
            source_sha256=native.PINNED | native.spatial.PINNED,
            scope=(
                "Radial component returns full membrane axis; native target assignment "
                "cannot take this subset"
            ),
        ),
    )


def test_multiple_spatial_pulses_require_a_single_declared_coordinate_frame():
    spec, point, plan = inputs()
    row = plan.pulses[0]
    other_ion = next(x for x in point.origin.binding.component.ion_ids if x != row.ion_id)
    second = replace(row, ion_id=other_ion)
    good = schedule.bind(spec, point.origin.binding, point.initial_component, pulses=(row, second))
    assert len(good.pulses) == 2
    parameters = asdict(row.spatial_modulator)
    parameters.pop("identity")
    parameters["centre_m"] = tuple(x + 2.0**-20 for x in parameters["centre_m"])
    bad = replace(second, spatial_scalar=None, spatial_modulator=spatial.bind(**parameters))
    with pytest.raises(ValueError, match="one complete intervention geometry"):
        schedule.bind(spec, point.origin.binding, point.initial_component, pulses=(row, bad))


@pytest.mark.parametrize("profile", ("INIT", "fast", "dynamic_off", "protein_off", "zero_level"))
def test_spatial_component_preserves_source_phase_and_draw_guards(profile):
    spec, point, _ = inputs(profile=profile, gradient="gradient_y", temporal=True)
    proposal = loop.propose(spec, point)
    result = loop.accept(spec, point, proposal, budget(proposal)).checkpoint
    assert result.component.stream.next_tick == point.component.stream.next_tick + int(
        perturb.dynamic_active(point.component.controls)
    )
    if profile == "INIT":
        exact_tree(result.component.diffusion, point.component.diffusion)


@pytest.mark.parametrize(
    "defect", ("coordinate", "coefficient", "resolved_factor", "resealed_geometry", "kind")
)
def test_restart_rechecks_geometry_and_resolved_factors_against_original_point(tmp_path, defect):
    spec, point, plan = inputs(gradient="gradient_r", temporal=True)
    path = persistence.write_protein_loop_checkpoint(tmp_path / "saved", spec, point)
    saved = json.loads((path / "schedule.json").read_text())
    row = saved["pulses"][0]
    if defect == "coordinate":
        row["spatial_modulator"]["membrane_midpoints_m"][1][0] += 1e-6
    elif defect == "coefficient":
        row["spatial_modulator"]["slope"] *= 2
    elif defect == "resolved_factor":
        row["spatial_scalar"][0] += 0.1
    elif defect == "kind":
        saved["kind"] = schedule.MODULATED_KIND
    else:
        parameters = asdict(plan.pulses[0].spatial_modulator)
        parameters.pop("identity")
        parameters["centre_m"] = (1e-6, 2e-6)
        changed = spatial.bind(**parameters)
        row["spatial_modulator"] = spatial.record(changed)
        row["spatial_scalar"] = spatial.evaluate(changed, xp=np).factor.tolist()
    saved["identity"] = digest({k: v for k, v in saved.items() if k != "identity"})
    (path / "schedule.json").write_text(json.dumps(saved))
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["files"]["schedule.json"] = persistence._sha(path / "schedule.json")
    manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, NumericalError)):
        persistence.load_protein_loop_checkpoint(path)


@pytest.mark.parametrize("kind,law", CASES)
def test_coupled_spatial_events_restart_and_independent_carried_trajectories(tmp_path, kind, law):
    gradient = (
        "gradient_r"
        if kind in ("calcium", "clamped")
        else "gradient_y"
        if kind == "ionic" or law == "stable"
        else "gradient_x"
    )
    use_native = kind not in ("passive", "fuel") or law == "stable"
    temporal = kind in ("ionic", "calcium", "fuel", "clamped")
    prepared = inputs(kind, law, gradient=gradient, native_clock=use_native, temporal=temporal)
    spec, _, plan = prepared
    labels = (
        None
        if not use_native
        else source_calendar.evaluate(calendars.record(plan.native_calendar), solver="normal")[
            "event_label_s"
        ]
    )
    point = qualify_carried(
        tmp_path, kind, law, prepared=prepared, event_labels=labels, prefix="spatial-loop"
    )
    path = persistence.write_protein_loop_checkpoint(tmp_path / "complete", spec, point)
    resumed = persistence.load_protein_loop_checkpoint(path)
    assert resumed.checkpoint.identity == point.identity
    assert (
        resumed.checkpoint.schedule.pulses[0].spatial_modulator == plan.pulses[0].spatial_modulator
    )
    if use_native:
        with pytest.raises(loop.ProteinLoopRejected) as caught:
            loop.propose(spec, resumed.checkpoint)
        assert caught.value.stage == "preparation" and not caught.value.intervals
