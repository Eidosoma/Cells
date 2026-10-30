"""Complete held-block intervals, independent integration and exact restart."""

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells import physiology_block_checkpoint as io
from cells.core import physiology_block_control_step as step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_step as ordinary
from cells.core.grid import EventGrid
from cells.core.schedule import control_values, event_index
from cells.core.specs import ConfigError, digest, parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_block_control_view as blocks
from cells.models import physiology_permeability_view as view
from cells.processes import betse_global_controls as setters
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_checkpoint import assert_same_component
from tests.integration.test_physiology_tissue_step_checkpoint import hashes
from tests.unit.test_physiology_permeability_view import KINDS, exact_tree, fingerprints
from tests.unit.test_physiology_tissue_binding import arguments, component_state, definition
from validation.perturbations import global_controls_native as native
from validation.tissue import physiology_block_step_reference as reference


def fixture(kind="passive", *, padded=True, enabled=True):
    raw = definition(kind, padded=padded, reorder=not padded)
    refinement = 16 if kind == "passive" else 64
    raw["execution"]["dt"] /= refinement
    # Retain the source horizon while explicitly declaring the larger grid.
    # This changes a step-count capacity, never a physical/numerical tolerance.
    raw["execution"]["max_steps"] = raw["execution"]["max_steps"] * refinement + 1
    dt = raw["execution"]["dt"]
    if not padded:
        event = 0.75 * dt
        raw["experiment"]["membrane_controls"][0]["schedule"].append(
            dict(time=event, availability=0.35)
        )
        raw["experiment"]["observation_times"] = sorted(
            {*raw["experiment"]["observation_times"], event}
        )
    spec = parse_spec(raw)
    args = arguments(spec, reverse=True)
    args["membrane_thickness_m"] = {
        m.id: 2.0 ** (-28 - i % 3) for i, m in enumerate(spec.model.membranes)
    }
    tissue = units.bind_tissue(spec, **args)
    component = component_state(tissue)
    if padded:
        rng = np.random.RandomState(17)
        rng.normal()
        engine = perturb._native_stream(rng.get_state(), np.__version__)
    else:
        engine = perturb.StableCoordinates(17, 79)
    component = replace(
        component,
        stream=streams.new_stream(
            tissue.component, engine, stream_id="block-step", world_id=79, next_tick=101
        ),
        controls=replace(component.controls, phase="SIM"),
        diffusion=component.diffusion._replace(current_m2_s=component.diffusion.base_m2_s * 1.09),
    )
    pairs = {
        edge.id: tuple(
            next(m.id for m in spec.model.membranes if m.inside == cell)
            for cell in (edge.sender, edge.receiver)
        )
        for edge in spec.model.junctions
    }
    events = [
        setters.Event(
            "junction_block",
            0.25 * dt,
            1.75 * dt,
            2 * dt,
            target_ids=tuple(name for pair in pairs.values() for name in pair),
        )
    ]
    if kind != "passive":
        events.append(setters.Event("pump_block", 0.3 * dt, 1.4 * dt, 1.7 * dt))
    program = setters.bind(
        membrane_ids=tissue.component.membrane_ids,
        events=events,
        provenance="Manufactured held-block interval and restart comparison",
    )
    binding = blocks.bind(
        spec,
        tissue,
        program,
        junction_membrane_ids=pairs,
        provenance="Explicit sender/receiver contact pairs",
    )
    implementation = view.IMPLEMENTATIONS[type(spec.model)]
    state, layout = implementation.initial_values(spec)
    numeric = Checkpoint(state, layout, 0.0, 0, event_index(spec, 0.0))
    point = step.initialise(
        spec,
        numeric,
        tissue,
        component,
        binding,
        blocks.BlockState(np.ones(len(program.membrane_ids)), np.asarray(1.0)),
        events_enabled=enabled,
    )
    return spec, point, implementation


def plain(values):
    return {k: np.asarray(v).tolist() for k, v in values._asdict().items()}


def evidence(name, record, arrays=None):
    if root := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        directory = Path(root) / "block-step"
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / (name + ".json")).open("x") as stream:
            json.dump(
                record,
                stream,
                indent=2,
                sort_keys=True,
                allow_nan=False,
                default=lambda x: np.asarray(x).tolist(),
            )
            stream.write("\n")
        if arrays is not None:
            np.savez_compressed(directory / (name + ".npz"), **arrays)


def potential(field, runtime):
    values = field.potential_V
    return np.r_[
        values[: runtime.active.size][runtime.active],
        values[runtime.active.size :][runtime.outside_active],
    ]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("padded", (False, True))
def test_coupled_three_intervals_full_reference_and_restart(tmp_path, kind, padded):
    spec, point, implementation = fixture(kind, padded=padded)
    original_component, original_layout = point.component, point.numeric.layout
    source = io.write_block_checkpoint(tmp_path / "initial", spec, point)
    fractions = []
    for index in range(3):
        original_files = hashes(source)
        before = fingerprints(spec, point.numeric.state, point.numeric.layout, point.component)
        wanted = step.advance(spec, point)
        destination = tmp_path / f"step-{index}"
        resumed = io.advance_block_checkpoint(source, destination, point.tissue_binding)
        loaded = io.load_block_checkpoint(destination, point.tissue_binding)
        assert (
            step.record(loaded.checkpoint)
            == step.record(resumed.checkpoint)
            == step.record(wanted.checkpoint)
        )
        exact_tree(loaded.checkpoint.numeric.state, wanted.checkpoint.numeric.state)
        exact_tree(loaded.checkpoint.numeric.layout, original_layout)
        exact_tree(loaded.checkpoint.block_state, wanted.checkpoint.block_state)
        assert_same_component(loaded.checkpoint.component, original_component)
        assert hashes(source) == original_files
        assert (
            fingerprints(spec, point.numeric.state, point.numeric.layout, point.component) == before
        )
        after = wanted.checkpoint
        h = after.numeric.time - point.numeric.time
        args = dict(
            raw=spec.to_dict(),
            fields=point.numeric.state._asdict(),
            binding_record=units.binding_record(point.tissue_binding),
            current_diffusion_m2_s=point.component.diffusion.current_m2_s,
            block_binding=blocks.record(point.binding),
            block_state=plain(point.block_state),
            start_time_s=point.numeric.time,
            end_time_s=after.numeric.time,
            events_enabled=point.events_enabled,
        )
        coarse = reference.integrate(**args)
        tight = reference.integrate(**args, refinement=2)
        context, target = tight["context"], tight["state"]
        oracle = reference.physical.ORACLES[spec.to_dict()["model"]["id"]]
        actual = oracle.flatten(context, after.numeric.state._asdict())
        atol = oracle.flatten(
            context,
            {
                k: np.full(s, 3e-23 if k.endswith("_C") else 3e-12)
                for k, s in context["shapes"].items()
            },
        )
        budget = atol + 3e-10 * abs(target)
        table = control_values(spec, [point.numeric.time])
        held_base = type(table)(*(v[0] for v in table))
        runtime = view.evaluate(
            spec,
            point.numeric.state,
            point.numeric.layout,
            held_base,
            point.tissue_binding,
            point.component,
            step_s=h,
        ).runtime_layout
        phi = potential(
            implementation.field_values(
                after.numeric.state, wanted.admission["endpoint_control"], runtime, xp=np
            ),
            runtime,
        )
        phi_budget = 3e-13 + 3e-10 * abs(tight["endpoint_potential_V"])
        first = ordinary.array_rk4_step(
            point.numeric.state,
            wanted.preparation.effective_control,
            runtime,
            h / 2,
            implementation=implementation,
            xp=np,
        )
        second = ordinary.array_rk4_step(
            first.proposed_state,
            wanted.preparation.effective_control,
            runtime,
            h / 2,
            implementation=implementation,
            xp=np,
        )
        assert first.valid and second.valid
        refined = oracle.flatten(context, second.proposed_state._asdict())
        refined_phi = potential(
            implementation.field_values(
                second.proposed_state, wanted.admission["endpoint_control"], runtime, xp=np
            ),
            runtime,
        )
        errors = dict(
            state=float(np.max(abs(actual - target) / budget, initial=0)),
            potential=float(
                np.max(abs(phi - tight["endpoint_potential_V"]) / phi_budget, initial=0)
            ),
            reference=float(np.max(abs(coarse["state"] - target) / budget, initial=0)),
            reference_potential=float(
                np.max(
                    abs(coarse["endpoint_potential_V"] - tight["endpoint_potential_V"])
                    / phi_budget,
                    initial=0,
                )
            ),
            half_step=float(np.max(abs(refined - target) / budget, initial=0)),
            half_step_potential=float(
                np.max(abs(refined_phi - tight["endpoint_potential_V"]) / phi_budget, initial=0)
            ),
        )
        assert all(0 <= v <= (0.1 if k.startswith("reference") else 1) for k, v in errors.items())
        native_state = native.evaluate(
            setters.record(point.binding.program),
            dict(
                temperature_K=spec.model.temperature_K,
                boundary_voltage_V=[0.0] * 4,
                **plain(point.block_state),
            ),
            point.numeric.time,
            spec.model.temperature_K,
            events_enabled=point.events_enabled,
        )
        assert plain(after.block_state) == {k: native_state[k] for k in after.block_state._fields}
        fractions.append(after.block_state.junction_available.copy())
        evidence(
            f"interval-{kind}-{padded}-{index}",
            dict(
                parameters=args,
                errors=errors,
                native_setter=native_state,
                source_sha256=native.PINNED,
                reference_block_state=tight["block_state"],
                actual_block_state=plain(after.block_state),
                reference_evaluations=[coarse["evaluations"], tight["evaluations"]],
                held_control=plain(wanted.preparation.effective_control),
                endpoint_control=plain(wanted.admission["endpoint_control"]),
                ordinary_checks=dict(wanted.admission["ordinary_balance_checks"]),
                runtime_checks=dict(wanted.admission["runtime_balance_checks"]),
                stage_energy_residual_pJ_s=[
                    float(s.energy_rate_residual_pJ_s) for s in wanted.trial.status
                ],
                checkpoint=step.record(after),
                complete_restart_exact=True,
                original_source_files_preserved=True,
                component_and_rng_unchanged=True,
                scope="Three original held-control intervals; manufactured numerical comparison",
                biological_cases=0,
            ),
            dict(
                actual=actual,
                tight=target,
                coarse=coarse["state"],
                budget=budget,
                actual_phi=phi,
                tight_phi=tight["endpoint_potential_V"],
                coarse_phi=coarse["endpoint_potential_V"],
                phi_budget=phi_budget,
                half_step=refined,
                half_step_phi=refined_phi,
            ),
        )
        source, point = destination, after
    assert any(not np.array_equal(fractions[0], v) for v in fractions[1:])
    a, b = original_component.stream, loaded.checkpoint.component.stream
    for site in ("microtubule_gaussian", "protein_flux", "boundary_choice"):
        x, a = streams.draw(a, point.tissue_binding.component, site=site)
        y, b = streams.draw(b, point.tissue_binding.component, site=site)
        np.testing.assert_array_equal(x.values, y.values, strict=True)
        assert streams.stream_record(a) == streams.stream_record(b)


@pytest.mark.parametrize("kind", KINDS)
def test_disabled_events_reproduce_the_existing_ordinary_interval_exactly(kind, monkeypatch):
    spec, point, _ = fixture(kind, enabled=False)
    monkeypatch.setattr(streams, "draw", lambda *a, **k: pytest.fail("Unexpected random draw"))
    expected = ordinary.advance(spec, point.numeric, point.tissue_binding, point.component)
    actual = step.advance(spec, point)
    exact_tree(actual.checkpoint.numeric.state, expected.checkpoint.state)
    exact_tree(actual.checkpoint.block_state, point.block_state)
    assert actual.checkpoint.numeric.time == expected.checkpoint.time


def test_late_asymmetric_event_keeps_last_accepted_restart_and_trial(tmp_path):
    spec, point, _ = fixture()
    dt = spec.execution.dt
    program = setters.bind(
        membrane_ids=point.binding.program.membrane_ids,
        events=(
            setters.Event(
                "junction_block",
                0.5 * dt,
                1.5 * dt,
                0.01 * dt,
                target_ids=(point.binding.junction_membranes[0][1],),
            ),
        ),
        provenance="Late source-valid asymmetric junction block",
    )
    binding = blocks.bind(
        spec,
        point.tissue_binding,
        program,
        junction_membrane_ids={j: (a, b) for j, a, b in point.binding.junction_membranes},
        provenance=point.binding.provenance,
    )
    point = step.initialise(
        spec,
        point.numeric,
        point.tissue_binding,
        point.component,
        binding,
        point.block_state,
        events_enabled=True,
    )
    point = step.advance(spec, point).checkpoint
    source = io.write_block_checkpoint(tmp_path / "accepted", spec, point)
    original = hashes(source)
    destination = tmp_path / "refused"
    with pytest.raises(step.BlockStepRejected) as caught:
        io.advance_block_checkpoint(source, destination, point.tissue_binding)
    failure = caught.value
    assert failure.stage == "left_event_preparation" and failure.trial is None
    assert failure.control_failure is not None and failure.control_failure.trial.physical_domain
    assert not destination.exists() and hashes(source) == original
    assert step.record(
        io.load_block_checkpoint(source, point.tissue_binding).checkpoint
    ) == step.record(point)
    evidence(
        "late-asymmetric-refusal",
        dict(
            accepted_checkpoint=step.record(point),
            failure_stage=failure.stage,
            source_valid_trial=plain(failure.control_failure.trial.state),
            source_files_unchanged=True,
            destination_absent=True,
            rng_unchanged=True,
        ),
    )


@pytest.mark.parametrize("defect", ("block", "component", "clock", "enable", "origin", "end"))
def test_stale_or_incomplete_association_refuses_before_commit(defect):
    spec, point, _ = fixture()
    original = step.record(point)
    kwargs = {}
    if defect == "block":
        wrong = replace(
            point, block_state=point.block_state._replace(pump_available=np.asarray(0.5))
        )
    elif defect == "component":
        wrong = replace(point, component=replace(point.component, time_s=1.0))
    elif defect == "clock":
        wrong = replace(point, numeric=replace(point.numeric, time=0.5 * spec.execution.dt))
    elif defect == "enable":
        wrong = replace(point, events_enabled=1)
    elif defect == "origin":
        wrong = replace(point, origin_step_index=-1)
    else:
        wrong = point
        kwargs["end_time_s"] = 2 * EventGrid(spec)[1]
    with pytest.raises(step.BlockStepRejected):
        step.advance(spec, wrong, **kwargs)
    assert step.record(point) == original


@pytest.mark.parametrize("kind", ("directory", "file", "symlink"))
def test_existing_destination_refuses_before_loading(tmp_path, monkeypatch, kind):
    target = tmp_path / "existing"
    if kind == "directory":
        target.mkdir()
    elif kind == "file":
        target.write_text("keep")
    else:
        target.symlink_to(tmp_path / "absent")
    monkeypatch.setattr(io, "load_block_checkpoint", lambda *a, **k: pytest.fail("Loaded source"))
    with pytest.raises(FileExistsError):
        io.advance_block_checkpoint(tmp_path / "unused", target, None)


@pytest.mark.parametrize("defect", ("hash", "state", "clock", "binding", "partial", "boolean"))
def test_saved_blocker_owner_clock_and_state_corruption_refuses(tmp_path, defect):
    spec, point, _ = fixture()
    source = io.write_block_checkpoint(tmp_path / "source", spec, point)
    original = hashes(source)
    target = tmp_path / "corrupt"
    shutil.copytree(source, target)
    manifest = json.loads((target / "manifest.json").read_text())
    saved = json.loads((target / "block.json").read_text())
    if defect == "clock":
        manifest["checkpoint"]["clock_policy"] = "different_clock"
    elif defect == "partial":
        manifest["complete"] = False
    elif defect == "binding":
        saved["binding"]["program"]["events"][0]["change_s"] *= 2
    else:
        saved["state"]["pump_available"] = True if defect == "boolean" else 0.5
    (target / "block.json").write_text(json.dumps(saved))
    if defect != "hash":
        manifest["files"]["block.json"] = io.paired._sha(target / "block.json")
        manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
    (target / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ConfigError):
        io.load_block_checkpoint(target, point.tissue_binding)
    assert hashes(source) == original


def test_source_change_after_numerical_work_refuses_publication(tmp_path, monkeypatch):
    spec, point, _ = fixture()
    source = io.write_block_checkpoint(tmp_path / "source", spec, point)
    original = hashes(source)
    advance = step.advance

    def changed(*args, **kwargs):
        result = advance(*args, **kwargs)
        monkeypatch.setattr(io, "source_hashes", lambda: {"changed.py": "0" * 64})
        return result

    monkeypatch.setattr(step, "advance", changed)
    target = tmp_path / "refused"
    with pytest.raises(ConfigError, match="Source differs"):
        io.advance_block_checkpoint(source, target, point.tissue_binding)
    assert not target.exists() and hashes(source) == original
