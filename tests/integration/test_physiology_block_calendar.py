"""Native-label blocker calls, complete carried references and atomic restart."""

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells import physiology_block_calendar_io as io
from cells.core import physiology_block_calendar as calls
from cells.core import physiology_block_control_step as steps
from cells.core import physiology_native_calendar as clocks
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core.specs import ConfigError, digest
from cells.models import physiology_block_control_view as blocks
from cells.processes import betse_global_controls as setters
from tests.integration.test_physiology_block_step import fixture as ordinary_fixture
from tests.integration.test_physiology_block_step import plain, potential
from tests.integration.test_physiology_checkpoint import assert_same_component
from tests.integration.test_physiology_tissue_step_checkpoint import hashes
from tests.unit.test_physiology_permeability_view import KINDS, exact_tree
from validation.perturbations import global_controls_native as native
from validation.perturbations import physiology_calendar_native as native_clock
from validation.tissue import physiology_block_calendar_reference as reference


def fixture(kind="passive", *, phase="SIM", padded=False):
    spec, point, implementation = ordinary_fixture(kind, padded=padded, enabled=False)
    calendar = clocks.bind(
        phase=phase,
        step_count=3,
        dt_s=2 * spec.execution.dt,
        provenance="Manufactured original three-call blocker calendar",
    )
    component = replace(
        point.component, controls=replace(point.component.controls, phase=phase, dt_s=calendar.dt_s)
    )
    state = point.block_state
    if phase == "INIT":
        state = blocks.BlockState(
            np.full_like(state.junction_available, 0.6),
            np.asarray(1.0 if kind == "passive" else 0.7),
        )
    checkpoint = calls.initialise(
        spec, point.numeric, point.tissue_binding, component, point.binding, state, calendar
    )
    return spec, checkpoint, implementation


def evidence(name, payload, arrays=None):
    if root := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        directory = Path(root) / "block-calendar"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / (name + ".json")).open("x") as stream:
            json.dump(
                payload,
                stream,
                indent=2,
                sort_keys=True,
                allow_nan=False,
                default=lambda x: np.asarray(x).tolist(),
            )
            stream.write("\n")
        if arrays is not None:
            np.savez_compressed(directory / (name + ".npz"), **arrays)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("phase", ("SIM", "INIT"))
def test_coupled_native_calendar_carried_reference_and_restart(tmp_path, kind, phase):
    padded = (KINDS.index(kind) % 2 == 0) == (phase == "INIT")
    spec, checkpoint, implementation = fixture(kind, phase=phase, padded=padded)
    point = checkpoint.point
    original_component, original_layout = point.component, point.numeric.layout
    params = dict(
        raw=spec.to_dict(),
        fields=plain(point.numeric.state),
        binding_record=units.binding_record(point.tissue_binding),
        current_diffusion_m2_s=point.component.diffusion.current_m2_s,
        block_binding=blocks.record(point.binding),
        block_state=plain(point.block_state),
        calendar=clocks.record(checkpoint.calendar),
    )
    coarse = reference.integrate(**params)
    tight = reference.integrate(**params, refinement=2)
    oracle = reference.intervals.physical.ORACLES[spec.to_dict()["model"]["id"]]
    native_calendar = {
        solver: native_clock.evaluate(params["calendar"], solver=solver)
        for solver in ("normal", "fast")
    }
    source = io.write_calendar_checkpoint(tmp_path / "initial", spec, checkpoint)
    rows, arrays = [], {}
    for index in range(3):
        original_files = hashes(source)
        before = calls.record(checkpoint)
        wanted = calls.advance(spec, checkpoint)
        destination = tmp_path / f"call-{index}"
        resumed = io.advance_calendar_checkpoint(source, destination, point.tissue_binding)
        loaded = io.load_calendar_checkpoint(destination, point.tissue_binding)
        assert (
            calls.record(loaded.checkpoint)
            == calls.record(resumed.checkpoint)
            == calls.record(wanted.checkpoint)
        )
        after = wanted.checkpoint.point
        exact_tree(loaded.checkpoint.point.numeric.state, after.numeric.state)
        exact_tree(loaded.checkpoint.point.block_state, after.block_state)
        exact_tree(loaded.checkpoint.point.numeric.layout, original_layout)
        assert_same_component(loaded.checkpoint.point.component, original_component)
        assert hashes(source) == original_files and calls.record(checkpoint) == before
        assert loaded.checkpoint.calendar == checkpoint.calendar
        for solver in ("normal", "fast"):
            assert (
                wanted.admission["event_label_s"] == native_calendar[solver]["event_label_s"][index]
            )
            if phase == "SIM":
                assert (
                    wanted.admission["event_label_s"]
                    == native_calendar[solver]["event_call_labels_s"][index]
                )
            else:
                assert native_calendar[solver]["event_call_labels_s"] == []
        assert wanted.admission["elapsed_end_s"] == (index + 1) * checkpoint.calendar.dt_s
        assert wanted.admission["declared_duration_s"] == checkpoint.calendar.dt_s
        assert len(wanted.intervals) == tight[index]["physical_subintervals"]
        native_setter = native.evaluate(
            params["block_binding"]["program"],
            dict(
                temperature_K=spec.model.temperature_K,
                boundary_voltage_V=[0.0] * 4,
                **plain(checkpoint.point.block_state),
            ),
            wanted.admission["event_label_s"],
            spec.model.temperature_K,
            events_enabled=phase == "SIM",
        )
        assert plain(after.block_state) == {k: native_setter[k] for k in after.block_state._fields}
        for key in after.block_state._fields:
            np.testing.assert_allclose(
                getattr(after.block_state, key),
                tight[index]["block_state"][key],
                rtol=0,
                atol=64 * np.finfo(np.float64).eps,
            )
        if phase == "INIT":
            exact_tree(after.block_state, checkpoint.point.block_state)
        elif index == 1:
            wrong_time = native.evaluate(
                params["block_binding"]["program"],
                dict(
                    temperature_K=spec.model.temperature_K,
                    boundary_voltage_V=[0.0] * 4,
                    **plain(checkpoint.point.block_state),
                ),
                checkpoint.point.numeric.time,
                spec.model.temperature_K,
                events_enabled=True,
            )
            assert native_setter["junction_available"] != wrong_time["junction_available"]
        target, context = tight[index]["state"], tight[index]["context"]
        actual = oracle.flatten(context, after.numeric.state._asdict())
        atol = oracle.flatten(
            context,
            {
                k: np.full(s, 3e-23 if k.endswith("_C") else 3e-12)
                for k, s in context["shapes"].items()
            },
        )
        budget = atol + 3e-10 * abs(target)
        runtime = after.numeric.layout._replace(
            membrane_permeability=units.component_permeability(
                after.component, after.tissue_binding
            ).current_m_s
        )
        right = wanted.intervals[-1].admission["endpoint_control"]
        phi = potential(
            implementation.field_values(after.numeric.state, right, runtime, xp=np), runtime
        )
        phi_budget = 3e-13 + 3e-10 * abs(tight[index]["endpoint_potential_V"])
        errors = dict(
            state=float(np.max(abs(actual - target) / budget, initial=0)),
            potential=float(
                np.max(abs(phi - tight[index]["endpoint_potential_V"]) / phi_budget, initial=0)
            ),
            reference=float(np.max(abs(coarse[index]["state"] - target) / budget, initial=0)),
            reference_potential=float(
                np.max(
                    abs(
                        coarse[index]["endpoint_potential_V"] - tight[index]["endpoint_potential_V"]
                    )
                    / phi_budget,
                    initial=0,
                )
            ),
        )
        assert all(0 <= v <= (0.1 if k.startswith("reference") else 1) for k, v in errors.items())
        rows.append(
            dict(
                admission=dict(wanted.admission),
                checkpoint=calls.record(wanted.checkpoint),
                errors=errors,
                native_setter=native_setter,
                actual_block_state=plain(after.block_state),
                reference_block_state=tight[index]["block_state"],
                reference_event_label_s=tight[index]["event_label_s"],
                reference_evaluations=[coarse[index]["evaluations"], tight[index]["evaluations"]],
                intervals=[
                    dict(
                        start_time_s=row.admission["event_time_s"],
                        step_s=row.admission["step_s"],
                        ordinary_checks=dict(row.admission["ordinary_balance_checks"]),
                        runtime_checks=dict(row.admission["runtime_balance_checks"]),
                        held_control=plain(row.preparation.effective_control),
                        endpoint_control=plain(row.admission["endpoint_control"]),
                        stage_energy_residual_pJ_s=[
                            float(s.energy_rate_residual_pJ_s) for s in row.trial.status
                        ],
                    )
                    for row in wanted.intervals
                ],
                complete_restart_exact=True,
                original_source_files_preserved=True,
                component_and_rng_unchanged=True,
            )
        )
        values = dict(
            actual=actual,
            tight=target,
            coarse=coarse[index]["state"],
            budget=budget,
            actual_phi=phi,
            tight_phi=tight[index]["endpoint_potential_V"],
            coarse_phi=coarse[index]["endpoint_potential_V"],
            phi_budget=phi_budget,
        )
        arrays.update({f"call{index}_{key}": value for key, value in values.items()})
        source, checkpoint = destination, wanted.checkpoint
    assert checkpoint.call_index == 3
    with pytest.raises(calls.CalendarRejected, match="no remaining event call"):
        calls.advance(spec, checkpoint)
    a, b = original_component.stream, loaded.checkpoint.point.component.stream
    for site in ("microtubule_gaussian", "protein_flux", "boundary_choice"):
        x, a = streams.draw(a, point.tissue_binding.component, site=site)
        y, b = streams.draw(b, point.tissue_binding.component, site=site)
        np.testing.assert_array_equal(x.values, y.values, strict=True)
        assert streams.stream_record(a) == streams.stream_record(b)
    evidence(
        f"trajectory-{phase}-{kind}",
        dict(
            parameters=params,
            calls=rows,
            native_calendar=native_calendar,
            native_source_sha256=native.PINNED | native_clock.PINNED,
            padded=padded,
            independent_trajectories_carried_from_initial=True,
            scope="Three native blocker calls with held component/RNG and original subintervals",
            biological_cases=0,
        ),
        arrays,
    )


def test_late_native_event_refuses_without_losing_parent_or_raw_trial(tmp_path):
    spec, checkpoint, _ = fixture(padded=True)
    point, dt = checkpoint.point, checkpoint.calendar.dt_s
    program = setters.bind(
        membrane_ids=point.binding.program.membrane_ids,
        events=(
            setters.Event(
                "junction_block",
                0.5 * dt,
                2 * dt,
                0.01 * dt,
                target_ids=(point.binding.junction_membranes[0][1],),
            ),
        ),
        provenance="Late asymmetric native-label event",
    )
    binding = blocks.bind(
        spec,
        point.tissue_binding,
        program,
        junction_membrane_ids={j: (a, b) for j, a, b in point.binding.junction_membranes},
        provenance=point.binding.provenance,
    )
    checkpoint = calls.initialise(
        spec,
        point.numeric,
        point.tissue_binding,
        point.component,
        binding,
        point.block_state,
        checkpoint.calendar,
    )
    checkpoint = calls.advance(spec, checkpoint).checkpoint
    source = io.write_calendar_checkpoint(tmp_path / "accepted", spec, checkpoint)
    original = hashes(source)
    target = tmp_path / "refused"
    with pytest.raises(calls.CalendarRejected) as caught:
        io.advance_calendar_checkpoint(source, target, point.tissue_binding)
    failure = caught.value
    assert failure.stage == "native_event_preparation" and failure.completed == ()
    assert isinstance(failure.failure, blocks.BlockControlRejected)
    assert failure.failure.trial.physical_domain
    assert hashes(source) == original and not target.exists()
    assert calls.record(
        io.load_calendar_checkpoint(source, point.tissue_binding).checkpoint
    ) == calls.record(checkpoint)
    evidence(
        "late-asymmetric-refusal",
        dict(
            accepted_checkpoint=calls.record(checkpoint),
            calendar=clocks.record(checkpoint.calendar),
            event_label_s=clocks.event_label_s(checkpoint.calendar, 1),
            failure_stage=failure.stage,
            source_valid_trial=plain(failure.failure.trial.state),
            source_files_unchanged=True,
            destination_absent=True,
            rng_unchanged=True,
        ),
    )


def test_mid_call_failure_retains_speculative_steps_and_original_parent(tmp_path, monkeypatch):
    spec, checkpoint, _ = fixture(padded=True)
    source = io.write_calendar_checkpoint(tmp_path / "parent", spec, checkpoint)
    original = hashes(source)
    advance = steps.advance
    count = 0

    def fail_second(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise steps.BlockStepRejected(
                "Injected second-interval refusal", source=args[1], stage="test_injection"
            )
        return advance(*args, **kwargs)

    monkeypatch.setattr(steps, "advance", fail_second)
    target = tmp_path / "partial"
    with pytest.raises(calls.CalendarRejected) as caught:
        io.advance_calendar_checkpoint(source, target, checkpoint.point.tissue_binding)
    failure = caught.value
    assert failure.stage == "physical_subintervals" and len(failure.completed) == 1
    assert failure.failure.stage == "test_injection"
    assert calls.record(failure.source) == calls.record(checkpoint)
    assert failure.completed[0].checkpoint.numeric.time > checkpoint.point.numeric.time
    assert failure.preparation is not None and hashes(source) == original and not target.exists()
    evidence(
        "mid-call-atomicity",
        dict(
            original_checkpoint=calls.record(checkpoint),
            speculative=steps.record(failure.completed[0].checkpoint),
            failure_stage=failure.stage,
            inner_failure_stage=failure.failure.stage,
            injected_framework_failure=True,
            committed_calls=0,
            source_files_unchanged=True,
            destination_absent=True,
            rng_unchanged=True,
        ),
    )


@pytest.mark.parametrize(
    "defect",
    (
        "cursor",
        "origin",
        "phase",
        "duration",
        "calendar",
        "inner_enable",
        "inner_clock",
        "boolean",
        "end",
    ),
)
def test_complete_clock_association_refuses_before_any_setter(defect, monkeypatch):
    spec, checkpoint, _ = fixture()
    point, calendar = checkpoint.point, checkpoint.calendar
    if defect == "cursor":
        wrong = calls._seal(replace(checkpoint, call_index=1))
    elif defect == "origin":
        wrong = calls._seal(replace(checkpoint, origin_call_index=1))
    elif defect in ("phase", "duration"):
        controls = replace(
            point.component.controls,
            **({"phase": "INIT"} if defect == "phase" else {"dt_s": calendar.dt_s / 2}),
        )
        wrong = calls._seal(
            replace(
                checkpoint,
                point=steps._seal(
                    replace(point, component=replace(point.component, controls=controls))
                ),
            )
        )
    elif defect == "calendar":
        wrong = replace(checkpoint, calendar=replace(calendar, step_count=2))
    elif defect == "inner_enable":
        wrong = calls._seal(
            replace(checkpoint, point=steps._seal(replace(point, events_enabled=True)))
        )
    elif defect == "inner_clock":
        wrong = calls._seal(
            replace(
                checkpoint,
                point=steps._seal(
                    replace(point, numeric=replace(point.numeric, time=spec.execution.dt))
                ),
            )
        )
    elif defect == "boolean":
        wrong = calls._seal(replace(checkpoint, call_index=False))
    else:
        replacement = clocks.bind(
            phase="SIM", step_count=3, dt_s=2.1 * spec.execution.dt, provenance="Off-grid calls"
        )
        component = replace(
            point.component, controls=replace(point.component.controls, dt_s=replacement.dt_s)
        )
        wrong = calls._seal(
            replace(
                checkpoint,
                calendar=replacement,
                point=steps._seal(replace(point, component=component)),
            )
        )
    original_prepare = blocks.prepare

    def guard(*args, **kwargs):
        if kwargs["events_enabled"]:
            pytest.fail("Fired an event before complete clock association validation")
        return original_prepare(*args, **kwargs)

    monkeypatch.setattr(blocks, "prepare", guard)
    with pytest.raises(calls.CalendarRejected):
        calls.advance(spec, wrong)


@pytest.mark.parametrize("count", (0, 1))
def test_empty_or_single_call_and_terminal_restart(tmp_path, count):
    spec, checkpoint, _ = fixture(padded=True)
    point = checkpoint.point
    calendar = clocks.bind(
        phase="SIM",
        step_count=count,
        dt_s=checkpoint.calendar.dt_s,
        provenance="Bounded special calendar",
    )
    args = (
        spec,
        point.numeric,
        point.tissue_binding,
        point.component,
        point.binding,
        point.block_state,
        calendar,
    )
    if count == 0:
        with pytest.raises(ValueError, match="Empty calendars"):
            calls.initialise(*args)
        return
    one = calls.advance(spec, calls.initialise(*args))
    assert one.admission["event_label_s"] == 0.0
    source = io.write_calendar_checkpoint(tmp_path / "terminal", spec, one.checkpoint)
    restored = io.load_calendar_checkpoint(source, point.tissue_binding).checkpoint
    assert restored.call_index == 1 and restored.calendar.step_count == 1
    with pytest.raises(calls.CalendarRejected, match="no remaining event call"):
        calls.advance(spec, restored)


@pytest.mark.parametrize(
    "defect", ("hash", "calendar", "cursor", "policy", "partial", "boolean", "child")
)
def test_saved_calendar_and_owner_corruption_refuses(tmp_path, defect):
    spec, checkpoint, _ = fixture()
    source = io.write_calendar_checkpoint(tmp_path / "source", spec, checkpoint)
    original = hashes(source)
    target = tmp_path / "corrupt"
    shutil.copytree(source, target)
    manifest = json.loads((target / "manifest.json").read_text())
    calendar = json.loads((target / "calendar.json").read_text())
    if defect in ("hash", "calendar"):
        calendar["step_count"] = 2
    elif defect == "cursor":
        manifest["checkpoint"]["call_index"] = 1
    elif defect == "policy":
        manifest["checkpoint"]["clock_policy"] = "rebase_to_remaining_phase"
    elif defect == "partial":
        manifest["complete"] = False
    elif defect == "boolean":
        calendar["sample_stride"] = True
    else:
        (target / "point" / "block.json").write_text("{}")
    (target / "calendar.json").write_text(json.dumps(calendar))
    if defect != "hash":
        manifest["files"]["calendar.json"] = io.blocked.paired._sha(target / "calendar.json")
        manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
    (target / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ConfigError):
        io.load_calendar_checkpoint(target, checkpoint.point.tissue_binding)
    assert hashes(source) == original


@pytest.mark.parametrize("kind", ("directory", "file", "symlink"))
def test_existing_destination_refuses_before_load(tmp_path, monkeypatch, kind):
    target = tmp_path / "existing"
    if kind == "directory":
        target.mkdir()
    elif kind == "file":
        target.write_text("keep")
    else:
        target.symlink_to(tmp_path / "absent")
    monkeypatch.setattr(
        io, "load_calendar_checkpoint", lambda *a, **k: pytest.fail("Loaded source")
    )
    with pytest.raises(FileExistsError):
        io.advance_calendar_checkpoint(tmp_path / "unused", target, None)


def test_source_change_after_call_refuses_publication(tmp_path, monkeypatch):
    spec, checkpoint, _ = fixture(padded=True)
    source = io.write_calendar_checkpoint(tmp_path / "source", spec, checkpoint)
    original = hashes(source)
    advance = calls.advance

    def changed(*args, **kwargs):
        result = advance(*args, **kwargs)
        monkeypatch.setattr(io, "source_hashes", lambda: {"changed.py": "0" * 64})
        return result

    monkeypatch.setattr(calls, "advance", changed)
    target = tmp_path / "refused"
    with pytest.raises(ConfigError, match="Source differs"):
        io.advance_calendar_checkpoint(source, target, checkpoint.point.tissue_binding)
    assert hashes(source) == original and not target.exists()


def test_off_grid_next_call_does_not_invalidate_accepted_parent(tmp_path, monkeypatch):
    spec, checkpoint, _ = fixture(padded=False)
    point = checkpoint.point
    calendar = clocks.bind(
        phase="SIM",
        step_count=4,
        dt_s=0.75 * spec.execution.dt,
        provenance="First off-nominal control boundary; absent second native boundary",
    )
    component = replace(
        point.component, controls=replace(point.component.controls, dt_s=calendar.dt_s)
    )
    checkpoint = calls.initialise(
        spec,
        point.numeric,
        point.tissue_binding,
        component,
        point.binding,
        point.block_state,
        calendar,
    )
    accepted = calls.advance(spec, checkpoint).checkpoint
    assert accepted.point.numeric.time == calendar.dt_s
    source = io.write_calendar_checkpoint(tmp_path / "accepted", spec, accepted)
    assert calls.record(
        io.load_calendar_checkpoint(source, point.tissue_binding).checkpoint
    ) == calls.record(accepted)
    original = hashes(source)
    monkeypatch.setattr(streams, "draw", lambda *a, **k: pytest.fail("Unexpected random draw"))
    target = tmp_path / "refused"
    with pytest.raises(calls.CalendarRejected) as caught:
        io.advance_calendar_checkpoint(source, target, point.tissue_binding)
    assert caught.value.stage == "source_admission" and caught.value.preparation is None
    assert not target.exists() and hashes(source) == original
