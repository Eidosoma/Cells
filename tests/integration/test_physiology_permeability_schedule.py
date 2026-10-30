"""Scheduled modifiers/pulses, actual charged trajectories and native arithmetic."""

import json
from dataclasses import replace
from functools import lru_cache

import numpy as np
import pytest

from cells import physiology_protein_loop_io as persistence
from cells.core import physiology_permeability_schedule as schedule
from cells.core import physiology_perturbation_phases as phases
from cells.core import physiology_protein_loop as loop
from cells.core import physiology_protein_transition as transition
from cells.core import physiology_random_streams as streams
from cells.core.errors import NumericalError
from cells.core.specs import digest
from tests.integration.test_physiology_protein_charge_view import active_nodes
from tests.integration.test_physiology_protein_loop import budget, initial, loop_input
from tests.integration.test_physiology_protein_transition import plain_component
from tests.unit.test_physiology_permeability_view import exact_tree
from tests.unit.test_physiology_tissue_step import evidence
from validation.perturbations import permeability_schedule_native as native
from validation.tissue import physiology_protein_loop_reference as reference


@lru_cache(maxsize=16)
def inputs(kind="passive", law="native", profile="normal"):
    spec, source = initial(kind, law, profile)
    component, binding = source.component, source.origin.binding
    dt = component.controls.dt_s
    base = component.diffusion.base_m2_s
    ion = next(
        name
        for name in ("K", "Na", "Cl", "Ca")
        if name in binding.component.ion_ids
        and np.any(base[binding.component.ion_ids.index(name)] > 0)
    )
    row = base[binding.component.ion_ids.index(ion)]
    targets = tuple(
        name for name, live in zip(binding.component.membrane_ids, row > 0, strict=True) if live
    )
    pulse = schedule.MembranePulse(
        ion,
        targets,
        0.25 * dt,
        1.7 * dt,
        0.35 * dt,
        0.2,
        tuple(0.8 + 0.05 * i for i in range(len(targets))),
        1.0,
        float(np.min(row[row > 0])),
        "Synthetic declared owners with pinned BETSE membrane-pulse shape",
    )
    plan = schedule.bind(
        spec,
        binding,
        component,
        changes=(
            schedule.BufferChange(1, base * 0.07, "Explicit modest increase"),
            schedule.BufferChange(2, -base * 0.025, "Explicit withdrawal"),
        ),
        pulses=(pulse,),
    )
    point = loop.initialise(
        spec,
        source.origin.seed,
        binding,
        source.origin.charge_reference,
        component,
        protein_species_id=source.origin.protein_species_id,
        valence=source.origin.valence,
        standard_concentration_mol_m3=1.0,
        schedule=plan,
    )
    return spec, point, plan


@pytest.mark.parametrize("kind", ("passive", "ionic", "calcium", "fuel"))
def test_native_buffer_arithmetic_and_no_random_or_clock_change(kind, monkeypatch):
    spec, point, plan = inputs(kind)
    component = point.component
    binding = point.origin.binding
    saved = schedule.record(plan)
    plain = plain_component(component)

    def forbidden(*args, **kwargs):
        pytest.fail("Event staging sampled randomness")

    monkeypatch.setattr(streams, "draw", forbidden)
    cases = []
    for index in (0, 1, 2, 3):
        staged = schedule.stage(plan, component, component, binding, index)
        prepared = phases.prepare(staged, binding.component)
        wanted = native.evaluate(
            saved, loop.held.units.binding_record(binding), plain, plain, index
        )
        for name, value in prepared.held_state.diffusion._asdict().items():
            np.testing.assert_array_equal(value, wanted[name])
        exact_tree(staged.protein, component.protein)
        assert staged.stream == component.stream and staged.time_s == component.time_s
        assert staged.loop_calls == component.loop_calls
        cases.append(
            dict(loop_index=index, actual=prepared.held_state.diffusion._asdict(), expected=wanted)
        )
    evidence(
        "permeability-native-" + kind,
        dict(
            plan=saved,
            binding=loop.held.units.binding_record(binding),
            initial=plain,
            cases=cases,
            scope=(
                "pinned targeted membrane blocks, constant dynamic modulator; supplied Cells labels"
            ),
        ),
    )


@pytest.mark.parametrize(
    "defect",
    (
        "duplicate",
        "unordered",
        "shape",
        "nan",
        "past",
        "terminal",
        "unknown_owner",
        "overlap",
        "width",
        "provenance",
        "source",
        "clock",
    ),
)
def test_plan_validation_rejects_incomplete_or_ambiguous_programs(defect):
    spec, point, plan = inputs()
    binding = point.origin.binding
    changes, pulses = list(plan.changes), list(plan.pulses)
    if defect == "duplicate":
        changes.append(changes[-1])
    elif defect == "unordered":
        changes.reverse()
    elif defect == "shape":
        changes[0] = replace(changes[0], scheduled_m2_s=np.ones(2))
    elif defect == "nan":
        changes[0] = replace(
            changes[0], scheduled_m2_s=np.full_like(changes[0].scheduled_m2_s, np.nan)
        )
    elif defect == "past":
        changes[0] = replace(changes[0], loop_index=-1)
    elif defect == "terminal":
        changes[0] = replace(changes[0], loop_index=10**8)
    elif defect == "unknown_owner":
        pulses[0] = replace(pulses[0], membrane_ids=("unknown",))
    elif defect == "overlap":
        pulses.append(pulses[0])
    elif defect == "width":
        pulses[0] = replace(pulses[0], change_s=0.0)
    elif defect == "provenance":
        changes[0] = replace(changes[0], provenance="")
    elif defect == "source":
        bad = replace(plan, initial_component_identity="0" * 64)
        bad = replace(bad, identity=schedule.record(bad)["identity"])
        with pytest.raises(ValueError):
            schedule.validate(bad, spec, binding, point.initial_component, 0)
        return
    else:
        bad = replace(plan, physiological_dt_s=2 * plan.physiological_dt_s)
        bad = replace(bad, identity=schedule.record(bad)["identity"])
        with pytest.raises(ValueError):
            schedule.validate(bad, spec, binding, point.initial_component, 0)
        return
    with pytest.raises((ValueError, TypeError)):
        schedule.bind(spec, binding, point.component, changes=changes, pulses=pulses)


CASES = (
    ("passive", "native"),
    ("ionic", "native"),
    ("calcium", "native"),
    ("fuel", "native"),
    ("passive", "stable"),
    ("clamped", "native"),
)


@pytest.mark.parametrize("kind,law", CASES)
def test_carried_scheduled_loops_restart_at_event_and_match_independent_trajectories(
    tmp_path, kind, law
):
    qualify_carried(tmp_path, kind, law)


def qualify_carried(
    tmp_path, kind, law, *, prepared=None, event_labels=None, prefix="scheduled-loop"
):
    """Shared coupled checks with unchanged budgets and independently supplied labels."""
    spec, origin, plan = inputs(kind, law) if prepared is None else prepared
    point = origin
    receipts = []
    for index in range(3):
        proposal = loop.propose(spec, point)
        assert proposal.permeability_staging["sampled_loop_index"] == index
        assert proposal.permeability_staging["sampled_time_s"] == (
            point.time if event_labels is None else event_labels[index]
        )
        if event_labels is not None:
            assert proposal.permeability_staging["nominal_start_s"] == point.time
            assert proposal.permeability_staging["nominal_duration_s"] == plan.physiological_dt_s
            assert (
                proposal.permeability_staging["native_calendar_identity"]
                == plan.native_calendar.identity
            )
        if index in (1, 2):
            path = persistence.write_protein_loop_checkpoint(tmp_path / str(index), spec, point)
            saved = persistence.load_protein_loop_checkpoint(path)
            assert saved.checkpoint.schedule.identity == plan.identity
            assert loop.propose(saved.spec, saved.checkpoint).identity == proposal.identity
        receipt = loop.accept(spec, point, proposal, budget(proposal))
        point = receipt.checkpoint
        assert point.component.loop_calls == origin.component.loop_calls + index + 1
        assert point.component.stream.next_tick == origin.component.stream.next_tick + index + 1
        assert point.schedule.identity == plan.identity
        exact_tree(point.layout, origin.layout)
        assert receipt.cumulative_accounting["valid"]
        receipts.append(receipt)
    assert not np.array_equal(
        receipts[0].checkpoint.component.diffusion.current_m2_s,
        receipts[1].checkpoint.component.diffusion.current_m2_s,
    )
    params = dict(
        raw=spec.to_dict(),
        fields=origin.state._asdict(),
        binding=loop.held.units.binding_record(origin.origin.binding),
        source_component=plain_component(origin.component),
        charge_reference=origin.origin.charge_reference.protein._asdict(),
        loops=[loop_input(spec, r.proposal) | dict(loop_index=i) for i, r in enumerate(receipts)],
        valence=origin.origin.valence,
        standard_concentration_mol_m3=1.0,
        schedule=schedule.record(plan),
    )
    normal = reference.integrate(**params)
    tight = reference.integrate(**params, refinement=2)
    errors = []
    arrays = {}
    for index, (receipt, target, less) in enumerate(
        zip(receipts, tight["endpoints"], normal["endpoints"], strict=True)
    ):
        oracle = reference.ionic.local.rates.permeability.ORACLES[params["raw"]["model"]["id"]]
        context = target["context"]
        actual = oracle.flatten(context, receipt.checkpoint.state._asdict())
        tolerance = oracle.flatten(
            context,
            {
                name: np.full(shape, 3e-23 if name.endswith("_C") else 3e-12)
                for name, shape in context["shapes"].items()
            },
        ) + 3e-10 * abs(target["state"])
        phi = active_nodes(origin.origin.seed, receipt.proposal.after_rates.field.potential_V)
        ptol = 3e-13 + 3e-10 * abs(target["potential_V"])
        row = dict(
            state=float(np.max(abs(actual - target["state"]) / tolerance)),
            reference=float(np.max(abs(less["state"] - target["state"]) / tolerance)),
            potential=float(np.max(abs(phi - target["potential_V"]) / ptol)),
            reference_potential=float(
                np.max(abs(less["potential_V"] - target["potential_V"]) / ptol)
            ),
        )
        for name, value in receipt.checkpoint.component.protein._asdict().items():
            wanted = target["component"]["protein"][name]
            row["protein/" + name] = float(
                np.max(abs(value - wanted) / (2e-14 + 5e-13 * abs(wanted)))
            )
            arrays[str(index) + "_actual_protein_" + name] = value
            arrays[str(index) + "_expected_protein_" + name] = wanted
        for name, value in dict(
            chemical_energy_change_pJ=receipt.proposal.thermodynamics.total_free_energy_change_pJ,
            capacitor_energy_change_pJ=receipt.proposal.electrical.capacitor_energy_change_pJ,
            clamp_work_pJ=receipt.proposal.electrical.clamp_work_pJ,
        ).items():
            wanted = target["work"][name]
            row["work/" + name] = abs(value - wanted) / (3e-14 + 3e-10 * abs(wanted))
            arrays[str(index) + "_actual_work_" + name] = np.asarray(value)
            arrays[str(index) + "_expected_work_" + name] = np.asarray(wanted)
        assert max(row.values()) <= 1, row
        assert max(row["reference"], row["reference_potential"]) <= 0.1
        errors.append(row)
        arrays.update(
            {
                str(index) + "_" + k: v
                for k, v in dict(
                    actual=actual,
                    expected=target["state"],
                    standard=less["state"],
                    budget=tolerance,
                    actual_phi=phi,
                    expected_phi=target["potential_V"],
                    standard_phi=less["potential_V"],
                    phi_budget=ptol,
                ).items()
            }
        )
    evidence(
        prefix + "-" + kind + "-" + law,
        dict(
            parameters=params,
            errors=errors,
            evaluations=[x["evaluations"] for x in tight["endpoints"]],
            checkpoints=[r.checkpoint.identity for r in receipts],
            budgets=[transition._record(r.budget) for r in receipts],
            cumulative=[transition._record(r.cumulative_accounting) for r in receipts],
            staging=[transition._record(r.proposal.permeability_staging) for r in receipts],
            independent_carried_histories=True,
            independent_rng_engine=False,
            biological_cases=0,
        ),
        arrays,
    )
    return point


@pytest.mark.parametrize("profile", ("INIT", "fast", "dynamic_off", "protein_off", "zero_level"))
def test_scheduled_component_retains_original_noise_guards(profile):
    spec, point, plan = inputs(profile=profile)
    source = point
    for _ in range(2):
        proposal = loop.propose(spec, point)
        point = loop.accept(spec, point, proposal, budget(proposal)).checkpoint
    draws = 2 if profile == "zero_level" else 0
    assert point.component.stream.next_tick == source.component.stream.next_tick + draws
    if profile == "INIT":
        exact_tree(point.component.diffusion, source.component.diffusion)
    else:
        assert not np.array_equal(
            point.component.diffusion.current_m2_s, source.component.diffusion.current_m2_s
        )


def test_invalid_later_modifier_refuses_before_draw_and_keeps_last_accepted_point(monkeypatch):
    spec, source = initial()
    binding = source.origin.binding
    plan = schedule.bind(
        spec,
        binding,
        source.component,
        changes=(
            schedule.BufferChange(
                1, -2 * source.component.diffusion.base_m2_s, "Deliberately invalid future trial"
            ),
        ),
    )
    point = loop.initialise(
        spec,
        source.origin.seed,
        binding,
        source.origin.charge_reference,
        source.component,
        protein_species_id=source.origin.protein_species_id,
        valence=source.origin.valence,
        standard_concentration_mol_m3=1.0,
        schedule=plan,
    )
    proposal = loop.propose(spec, point)
    one = loop.accept(spec, point, proposal, budget(proposal)).checkpoint

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid modifier consumed a draw")

    monkeypatch.setattr(streams, "draw", forbidden)
    with pytest.raises(loop.ProteinLoopRejected) as caught:
        loop.propose(spec, one)
    assert caught.value.packet is None and not caught.value.intervals
    assert caught.value.failure.held_state is not None
    assert one.component.stream.next_tick == point.component.stream.next_tick + 1


@pytest.mark.parametrize("defect", ("state", "preparation", "plan", "omitted_plan"))
def test_schedule_association_refuses_resealed_changes(defect):
    spec, point, plan = inputs()
    proposal = loop.propose(spec, point)
    if defect == "state":
        changed = replace(
            point.component,
            diffusion=point.component.diffusion._replace(
                scheduled_m2_s=point.component.diffusion.base_m2_s
            ),
        )
        bad = loop._seal(replace(point, component=changed))
        with pytest.raises((ValueError, NumericalError)):
            loop.validate(spec, bad)
    elif defect == "preparation":
        changed = phases.prepare(point.component, point.origin.binding.component)
        bad = replace(proposal, preparation=changed)
        bad = replace(bad, identity=loop.proposal_record(bad)["identity"])
        with pytest.raises(loop.ProteinLoopRejected):
            loop.accept(spec, point, bad, budget(proposal))
    else:
        changed = None if defect == "omitted_plan" else replace(plan, identity="0" * 64)
        bad = loop._seal(replace(point, schedule=changed))
        with pytest.raises((ValueError, NumericalError)):
            loop.validate(spec, bad)


@pytest.mark.parametrize("defect", ("missing", "bytes", "changed_pulse"))
def test_saved_schedule_is_required_and_corruption_refuses(tmp_path, defect):
    spec, point, _ = inputs()
    proposal = loop.propose(spec, point)
    point = loop.accept(spec, point, proposal, budget(proposal)).checkpoint
    path = persistence.write_protein_loop_checkpoint(tmp_path / "scheduled", spec, point)
    if defect == "missing":
        (path / "schedule.json").unlink()
    elif defect == "bytes":
        with (path / "schedule.json").open("a") as f:
            f.write("changed")
    else:
        saved = json.loads((path / "schedule.json").read_text())
        saved["pulses"][0]["on_s"] += 1
        (path / "schedule.json").write_text(json.dumps(saved))
        manifest = json.loads((path / "manifest.json").read_text())
        manifest["files"]["schedule.json"] = persistence._sha(path / "schedule.json")
        manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
        (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, OSError, NumericalError)):
        persistence.load_protein_loop_checkpoint(path)
