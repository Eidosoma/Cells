"""Repeated charged loops, cumulative work gates and independent carried ODEs."""

import json
from dataclasses import replace
from decimal import Decimal, localcontext
from functools import lru_cache

import numpy as np
import pytest

from cells import physiology_protein_loop_io as persistence
from cells.core import physiology_protein_loop as loop
from cells.core import physiology_protein_transition as transition
from cells.core import physiology_random_streams as streams
from cells.core.errors import NumericalError
from cells.core.specs import digest
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_protein_charge_view import active_nodes
from tests.integration.test_physiology_protein_transition import fixture, plain_component
from tests.unit.test_physiology_permeability_view import exact_tree
from tests.unit.test_physiology_tissue_step import control, evidence
from validation.tissue import physiology_protein_loop_reference as reference


@lru_cache(maxsize=16)
def initial(kind="passive", law="native", profile="normal", shift=0.0):
    spec, held, preparation, _ = fixture(kind, law, profile, shift)
    point = loop.initialise(
        spec,
        held.seed,
        held.binding,
        held.charge_reference,
        preparation.source_state,
        protein_species_id=held.protein_species_id,
        valence=held.valence,
        standard_concentration_mol_m3=1.0,
    )
    return spec, point


def budget(proposal, *, offset=0.0, dissipation=0.0):
    return transition.DrivingBudget(
        proposal.conditional_work.reversible_driving_work_pJ + dissipation + offset,
        dissipation,
        "Synthetic endpoint-consistent declaration; no physical driving law",
    )


@lru_cache(maxsize=12)
def first(kind="passive", law="native", profile="normal"):
    spec, point = initial(kind, law, profile)
    proposal = loop.propose(spec, point)
    return spec, point, loop.accept(spec, point, proposal, budget(proposal))


def loop_input(spec, proposal):
    packet = proposal.component_transition.packet
    return dict(
        prescribed_uniforms=None if packet is None else packet.values,
        intervals=[
            dict(
                duration_s=row.end_s - row.start_s,
                held_control=control(spec, row.start_s)._asdict(),
                endpoint_control=control(spec, row.end_s)._asdict(),
            )
            for row in proposal.intervals
        ],
    )


CASES = (
    ("passive", "native"),
    ("ionic", "native"),
    ("calcium", "native"),
    ("fuel", "native"),
    ("passive", "stable"),
    ("clamped", "native"),
)


@pytest.mark.parametrize("kind,law", CASES)
def test_two_carried_loops_restart_and_independent_refined_trajectories(tmp_path, kind, law):
    spec, source, one = first(kind, law)
    saved = persistence.write_protein_loop_checkpoint(tmp_path / "loop1", spec, one.checkpoint)
    loaded = persistence.load_protein_loop_checkpoint(saved)
    assert loaded.checkpoint.identity == one.checkpoint.identity
    second_proposal = loop.propose(spec, one.checkpoint)
    resumed_proposal = loop.propose(loaded.spec, loaded.checkpoint)
    assert resumed_proposal.identity == second_proposal.identity
    second_budget = budget(second_proposal)
    two = loop.accept(spec, one.checkpoint, second_proposal, second_budget)
    resumed = loop.accept(loaded.spec, loaded.checkpoint, resumed_proposal, second_budget)
    assert resumed.checkpoint.identity == two.checkpoint.identity
    exact_tree(resumed.checkpoint.state, two.checkpoint.state)
    exact_tree(two.checkpoint.layout, source.layout)
    path = persistence.write_protein_loop_checkpoint(tmp_path / "loop2", spec, two.checkpoint)
    assert (
        persistence.load_protein_loop_checkpoint(path).checkpoint.identity
        == two.checkpoint.identity
    )
    assert one.checkpoint.component.loop_calls == source.component.loop_calls + 1
    assert two.checkpoint.component.stream.next_tick == source.component.stream.next_tick + 2
    if law == "native":
        assert (
            json.loads(two.checkpoint.component.stream.rng.state_json)[3:]
            == json.loads(source.component.stream.rng.state_json)[3:]
        )
    params = dict(
        raw=spec.to_dict(),
        fields=source.state._asdict(),
        binding=loop.held.units.binding_record(source.origin.binding),
        source_component=plain_component(source.component),
        charge_reference=source.origin.charge_reference.protein._asdict(),
        loops=[loop_input(spec, r.proposal) for r in (one, two)],
        valence=source.origin.valence,
        standard_concentration_mol_m3=1.0,
    )
    standard = reference.integrate(**params)
    tight = reference.integrate(**params, refinement=2)
    arrays, errors = {}, []
    for index, (receipt, target, less) in enumerate(
        zip((one, two), tight["endpoints"], standard["endpoints"], strict=True)
    ):
        context = target["context"]
        oracle = reference.ionic.local.rates.permeability.ORACLES[params["raw"]["model"]["id"]]
        values = oracle.flatten(context, receipt.checkpoint.state._asdict())
        tolerance = oracle.flatten(
            context,
            {
                name: np.full(shape, 3e-23 if name.endswith("_C") else 3e-12)
                for name, shape in context["shapes"].items()
            },
        ) + 3e-10 * abs(target["state"])
        phi = active_nodes(source.origin.seed, receipt.proposal.after_rates.field.potential_V)
        ptol = 3e-13 + 3e-10 * abs(target["potential_V"])
        row = dict(
            state=float(np.max(abs(values - target["state"]) / tolerance)),
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
        works = dict(
            chemical_energy_change_pJ=receipt.proposal.thermodynamics.total_free_energy_change_pJ,
            capacitor_energy_change_pJ=receipt.proposal.electrical.capacitor_energy_change_pJ,
            clamp_work_pJ=receipt.proposal.electrical.clamp_work_pJ,
        )
        for name, value in works.items():
            wanted = target["work"][name]
            row["work/" + name] = abs(value - wanted) / (3e-14 + 3e-10 * abs(wanted))
            arrays[str(index) + "_actual_work_" + name] = np.asarray(value)
            arrays[str(index) + "_expected_work_" + name] = np.asarray(wanted)
        assert max(row.values()) <= 1, row
        assert max(row["reference"], row["reference_potential"]) <= 0.1
        assert receipt.cumulative_accounting["valid"]
        errors.append(row)
        arrays.update(
            {
                str(index) + "_" + k: v
                for k, v in dict(
                    actual=values,
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
    if kind == "fuel":
        assert np.any(two.checkpoint.state.energy_amount_increment_fmol != 0)
        assert np.any(two.checkpoint.state.regeneration_supplied_work_pJ != 0)
    if kind == "clamped":
        assert np.any(one.proposal.electrical.electrode_charge_change_C != 0)
        assert abs(one.proposal.electrical.clamp_work_pJ) > 1e-20
    evidence(
        "protein-loop-" + kind + "-" + law,
        dict(
            parameters=params,
            errors=errors,
            checkpoints=[one.checkpoint.identity, two.checkpoint.identity],
            budgets=[transition._record(r.budget) for r in (one, two)],
            ledgers=[transition._record(r.checkpoint.ledger) for r in (one, two)],
            cumulative=[transition._record(r.cumulative_accounting) for r in (one, two)],
            evaluations=[r["evaluations"] for r in tight["endpoints"]],
            independent_carried_histories=True,
            independent_rng_engine=False,
            biological_cases=0,
        ),
        arrays,
    )


@pytest.mark.parametrize("profile", ("INIT", "fast", "dynamic_off", "protein_off", "zero_level"))
def test_original_component_guards_across_repeated_loops(profile):
    spec, source, one = first(profile=profile)
    proposal = loop.propose(spec, one.checkpoint)
    two = loop.accept(spec, one.checkpoint, proposal, budget(proposal))
    draws = 2 if profile == "zero_level" else 0
    assert two.checkpoint.component.stream.next_tick == source.component.stream.next_tick + draws
    assert two.checkpoint.component.loop_calls == source.component.loop_calls + 2
    assert (
        proposal.component_transition.packet is not None
        if draws
        else proposal.component_transition.packet is None
    )
    exact_tree(two.checkpoint.component.protein, source.component.protein)


def test_accept_save_load_and_stale_parent_do_not_draw(tmp_path, monkeypatch):
    spec, point = initial()
    proposal = loop.propose(spec, point)

    def forbidden(*args, **kwargs):
        pytest.fail("Acceptance/save/load/stale parent consumed a random draw")

    monkeypatch.setattr(streams, "draw", forbidden)
    receipt = loop.accept(spec, point, proposal, budget(proposal))
    path = persistence.write_protein_loop_checkpoint(tmp_path / "saved", spec, receipt.checkpoint)
    assert (
        persistence.load_protein_loop_checkpoint(path).checkpoint.identity
        == receipt.checkpoint.identity
    )
    with pytest.raises(loop.ProteinLoopRejected) as caught:
        loop.accept(spec, receipt.checkpoint, proposal, budget(proposal))
    assert caught.value.stage == "proposal_association"


@pytest.mark.parametrize("kind", ("passive", "fuel"))
def test_locally_acceptable_budget_errors_cannot_accumulate_a_larger_global_limit(kind):
    spec, point = initial(kind)
    proposal = loop.propose(spec, point)
    limit = loop.validate(spec, point)["energy_limit_pJ"]
    one = loop.accept(spec, point, proposal, budget(proposal, offset=0.6 * limit))
    again = loop.propose(spec, one.checkpoint)
    with pytest.raises(loop.ProteinLoopRejected) as caught:
        loop.accept(spec, one.checkpoint, again, budget(again, offset=0.6 * limit))
    assert caught.value.stage == "cumulative_accounting"
    assert abs(caught.value.report["energy_residual_pJ"]) > limit
    assert caught.value.packet is again.component_transition.packet
    evidence(
        "protein-loop-cumulative-refusal-" + kind,
        dict(
            limit=limit,
            report=transition._record(caught.value.report),
            source=one.checkpoint.identity,
            failed_packet=perturb.draw_manifest(
                caught.value.packet, point.origin.binding.component
            ),
        ),
    )


def test_large_canceling_declared_totals_preserve_small_global_imbalance():
    spec, point = initial(profile="zero_level")
    proposal = loop.propose(spec, point)
    accepted = loop.accept(
        spec, point, proposal, transition.DrivingBudget(1e20, 1e20, "Synthetic cancellation")
    )
    with localcontext() as context:
        context.prec = 4096
        changed = str(Decimal(accepted.checkpoint.ledger.external_work_pJ) + Decimal("0.000001"))
    assert float(changed) == float(accepted.checkpoint.ledger.external_work_pJ)
    corrupt = loop._seal(
        replace(
            accepted.checkpoint,
            ledger=replace(accepted.checkpoint.ledger, external_work_pJ=changed),
        )
    )
    with pytest.raises(loop.ProteinLoopRejected):
        loop.validate(spec, corrupt)


@pytest.mark.parametrize("defect", ("state", "work", "packet", "stream", "clock"))
def test_resealed_proposal_changes_refuse_without_advancing_source(defect):
    spec, point, accepted = first()
    proposal = accepted.proposal
    if defect == "state":
        row = proposal.intervals[-1]
        state = row.trial.proposed_state
        changed = state._replace(amount_increment=state.amount_increment + 1e-3)
        intervals = (
            *proposal.intervals[:-1],
            replace(row, trial=row.trial._replace(proposed_state=changed)),
        )
        bad = replace(proposal, intervals=intervals)
    elif defect == "work":
        bad = replace(proposal, electrical=replace(proposal.electrical, clamp_work_pJ=1.0))
    elif defect == "packet":
        bad = replace(
            proposal, component_transition=replace(proposal.component_transition, packet=None)
        )
    else:
        component = proposal.component_transition.state
        component = replace(
            component,
            **(
                {"stream": point.component.stream}
                if defect == "stream"
                else {"time_s": component.time_s + 1}
            ),
        )
        bad = replace(
            proposal, component_transition=replace(proposal.component_transition, state=component)
        )
    bad = replace(bad, identity=loop.proposal_record(bad)["identity"])
    with pytest.raises(loop.ProteinLoopRejected):
        loop.accept(spec, point, bad, budget(proposal))
    assert point.component.stream.next_tick == 31


@pytest.mark.parametrize("defect", ("origin", "clock", "count", "ledger"))
def test_resealed_checkpoint_history_inconsistency_refuses(defect):
    spec, source, accepted = first()
    point = accepted.checkpoint
    if defect == "origin":
        changed = loop.held._seal(replace(point.origin, component=point.component))
        point = replace(point, origin=changed)
    elif defect == "clock":
        point = replace(point, component=replace(point.component, time_s=999.0))
    elif defect == "count":
        point = replace(point, loop_index=point.loop_index + 1)
    else:
        point = replace(point, ledger=replace(point.ledger, external_work_pJ="1"))
    point = loop._seal(point)
    with pytest.raises((ValueError, NumericalError)):
        loop.validate(spec, point)


@pytest.mark.parametrize("defect", ("partial", "bytes", "work", "clock"))
def test_restart_corruption_and_resealed_global_history_refuse(tmp_path, defect):
    spec, _, accepted = first()
    path = persistence.write_protein_loop_checkpoint(tmp_path / "saved", spec, accepted.checkpoint)
    if defect == "partial":
        (path / "manifest.json").unlink()
    elif defect == "bytes":
        with (path / "state.npz").open("ab") as handle:
            handle.write(b"corrupted")
    else:
        record = json.loads((path / "manifest.json").read_text())
        if defect == "work":
            record["checkpoint"]["ledger"]["external_work_pJ"] = "1"
        else:
            record["checkpoint"]["loop_index"] += 1
        record["checkpoint"]["identity"] = digest(
            {k: v for k, v in record["checkpoint"].items() if k != "identity"}
        )
        record["identity"] = digest({k: v for k, v in record.items() if k != "identity"})
        (path / "manifest.json").write_text(json.dumps(record))
    with pytest.raises((ValueError, OSError, NumericalError)):
        persistence.load_protein_loop_checkpoint(path)


def test_late_ionic_failure_retains_completed_intervals_without_random_draw(monkeypatch):
    spec, point = initial()
    original = loop.step.array_rk4_step
    calls = []

    def altered(*args, **kwargs):
        trial = original(*args, **kwargs)
        calls.append(trial)
        return trial if len(calls) == 1 else trial._replace(valid=np.asarray(False))

    def forbidden(*args, **kwargs):
        pytest.fail("Ionic failure consumed a protein draw")

    monkeypatch.setattr(loop.step, "array_rk4_step", altered)
    monkeypatch.setattr(streams, "draw", forbidden)
    with pytest.raises(loop.ProteinLoopRejected) as caught:
        loop.propose(spec, point)
    assert len(caught.value.intervals) == 1 and caught.value.trial is not None
    assert caught.value.packet is None


def test_failed_protein_trial_retains_packet_and_replays_same_source():
    spec, point = initial()
    component = replace(
        point.component, controls=replace(point.component.controls, dynamic_level_mol_m2_s=1e100)
    )
    bad = loop.initialise(
        spec,
        point.origin.seed,
        point.origin.binding,
        point.origin.charge_reference,
        component,
        protein_species_id=point.origin.protein_species_id,
        valence=point.origin.valence,
        standard_concentration_mol_m3=1.0,
    )
    failures = []
    for _ in range(2):
        with pytest.raises(loop.ProteinLoopRejected) as caught:
            loop.propose(spec, bad)
        failures.append(caught.value)
    assert failures[0].packet is not None and failures[0].intervals
    np.testing.assert_array_equal(failures[0].packet.values, failures[1].packet.values)
    assert failures[0].stream == failures[1].stream


@pytest.mark.parametrize("defect", ("negative_dissipation", "nan", "bool", "provenance"))
def test_invalid_budget_preserves_uncommitted_packet(defect):
    spec, point, receipt = first()
    declaration = replace(
        receipt.budget,
        **dict(
            negative_dissipation=dict(dissipated_free_energy_pJ=-1e-20),
            nan=dict(external_work_pJ=float("nan")),
            bool=dict(external_work_pJ=True),
            provenance=dict(provenance=""),
        )[defect],
    )
    with pytest.raises(loop.ProteinLoopRejected) as caught:
        loop.accept(spec, point, receipt.proposal, declaration)
    assert caught.value.packet is receipt.proposal.component_transition.packet
    assert point.component.stream.next_tick == 31


def test_shared_two_clamps_cumulative_accounting_under_common_voltage_shift():
    outputs = []
    for shift in (0.0, 1.75):
        spec, point = initial("clamped", shift=shift)
        for _ in range(2):
            proposal = loop.propose(spec, point)
            receipt = loop.accept(spec, point, proposal, budget(proposal))
            point = receipt.checkpoint
        outputs.append(point)
        assert receipt.cumulative_accounting["valid"]
    for a, b in zip(outputs[0].component.protein, outputs[1].component.protein, strict=True):
        np.testing.assert_array_equal(a, b)
    assert (
        abs(float(outputs[0].ledger.clamp_work_pJ) - float(outputs[1].ledger.clamp_work_pJ)) < 3e-14
    )
