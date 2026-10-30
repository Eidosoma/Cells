"""Real post-ion proposals, explicit drive budgets, independent work and replay."""

import hashlib
import json
from dataclasses import asdict, replace
from functools import lru_cache

import numpy as np
import pytest

from cells import physiology_protein_transition_io as receipt_io
from cells.core import physiology_perturbation_phases as phases
from cells.core import physiology_protein_charge_interval as held
from cells.core import physiology_protein_transition as transition
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.core.specs import digest, parse_spec
from cells.core.state import Checkpoint
from cells.models import physiology_permeability_view as view
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_protein_charge_view import active_nodes, changed_protein
from tests.integration.test_physiology_protein_checkpoint import inputs as held_inputs
from tests.unit.test_physiology_permeability_view import exact_tree, fingerprints
from tests.unit.test_physiology_tissue_binding import arguments, component_state
from tests.unit.test_physiology_tissue_step import KINDS, control, evidence
from validation.tissue import physiology_protein_transition_reference as reference
from validation.tissue import surface_dynamics_fixtures


@lru_cache(maxsize=24)
def fixture(kind="passive", law="native", profile="normal", shift=0.0):
    if kind != "clamped":
        spec, initial, implementation = held_inputs(kind)
        seed, binding, source = initial.seed, initial.binding, initial.component
    else:
        raw = surface_dynamics_fixtures.definition("clamped", padded=True)
        raw["execution"]["dt"] *= 0.125
        raw["execution"]["max_steps"] *= 8
        for row in raw["model"]["extracellular"]:
            row["volume_pL"] = 4.0
            # Both clamps share cell_0's capacitive component. Native membrane
            # flux can then redistribute electrode charge between them; an
            # isolated second clamp has exactly zero protein electrode work.
            row["reservoir"] = row["id"] in ("outside_0", "outside_1")
            row["boundary_potential_V"] = -0.004 if row["id"] == "outside_1" else 0.0
            if row["reservoir"]:
                row["boundary_potential_V"] += shift
        spec = parse_spec(raw)
        binding = units.bind_tissue(spec, **arguments(spec, reverse=True))
        source = component_state(binding)
        implementation = view.IMPLEMENTATIONS[type(spec.model)]
        state, layout = implementation.initial_values(spec)
        seed = Checkpoint(state, layout, 0.0, 0, 0)
    if law == "native":
        rng = np.random.RandomState(17)
        rng.normal()
        rng = perturb._native_stream(rng.get_state(), np.__version__)
    else:
        rng = perturb.StableCoordinates(17, 7)
    stream = streams.new_stream(
        binding.component, rng, stream_id="post-ion", world_id=7, next_tick=31
    )
    k = binding.component.kernel
    scale = max(
        np.max(np.sum(abs(k.cell_surface_map), axis=1) / k.cell_volume_m3),
        np.max(np.sum(abs(k.environment_surface_map), axis=1) / k.environment_effective_volume_m3),
    )
    controls = replace(
        source.controls,
        phase="SIM",
        solver="normal",
        dynamic_enabled=True,
        protein_enabled=True,
        dt_s=spec.execution.dt,
        dynamic_level_mol_m2_s=2e-5 / (spec.execution.dt * scale),
    )
    options = dict(
        normal={},
        INIT=dict(phase="INIT"),
        fast=dict(solver="fast"),
        dynamic_off=dict(dynamic_enabled=False),
        protein_off=dict(protein_enabled=False),
        zero_level=dict(dynamic_level_mol_m2_s=0.0),
    )
    controls = replace(controls, **options[profile])
    protein = source.protein._replace(
        cell_mol_m3=np.full(len(binding.component.cell_ids), 2**-10),
        environment_mol_m3=np.full(len(binding.component.environment_ids), 3 * 2**-10),
        membrane_mol_m3=np.full(len(binding.component.membrane_ids), 2**-10),
    )
    source = replace(
        source, protein=protein, controls=controls, stream=stream, time_s=0.004, loop_calls=3
    )
    preparation = phases.prepare(source, binding.component)
    anchor = changed_protein(binding, source)
    point = held.initialise(
        spec,
        seed,
        binding,
        anchor,
        preparation.held_state,
        protein_species_id="post-ion-protein",
        valence=-1,
    )
    while point.time < controls.dt_s:
        point = held.advance(spec, point).checkpoint
    return spec, point, preparation, implementation


def propose(spec, point, preparation):
    return transition.propose(
        spec, point, preparation, loop_index=0, standard_concentration_mol_m3=1.0
    )


def plain_component(component):
    return dict(
        protein=component.protein._asdict(),
        diffusion=component.diffusion._asdict(),
        controls=asdict(component.controls),
        time_s=component.time_s,
        loop_calls=component.loop_calls,
        stream_next_tick=component.stream.next_tick,
    )


def parameters(spec, point, preparation, proposal):
    packet = proposal.transition.packet
    return dict(
        raw=spec.to_dict(),
        fields=point.state._asdict(),
        binding=units.binding_record(point.binding),
        source_component=plain_component(preparation.source_state),
        charge_reference=point.charge_reference.protein._asdict(),
        prescribed_uniforms=None if packet is None else packet.values,
        endpoint_control=control(spec, point.time)._asdict(),
        valence=point.valence,
        standard_concentration_mol_m3=1.0,
    )


def compare(name, spec, point, preparation, proposal):
    params = parameters(spec, point, preparation, proposal)
    expected = reference.evaluate(**params)
    actual = dict(
        chemical_energy_change_pJ=proposal.thermodynamics.total_free_energy_change_pJ,
        capacitor_energy_change_pJ=proposal.electrical.capacitor_energy_change_pJ,
        clamp_work_pJ=proposal.electrical.clamp_work_pJ,
        conditional_reversible_work_pJ=proposal.conditional_work.reversible_driving_work_pJ,
    )
    energy_budget = {key: 3e-14 + 3e-10 * abs(expected["work"][key]) for key in actual}
    errors = {
        key: abs(value - expected["work"][key]) / energy_budget[key]
        for key, value in actual.items()
    }
    context = expected["context"]
    oracle = reference.rates.permeability.ORACLES[params["raw"]["model"]["id"]]
    rates = oracle.flatten(context, proposal.after_rates.derivative._asdict())
    rate_budget = oracle.flatten(
        context,
        {
            name: np.full(shape, 3e-23 if name.endswith("_C") else 3e-12)
            for name, shape in context["shapes"].items()
        },
    ) + 3e-10 * abs(expected["derivative"])
    errors["rates"] = float(np.max(abs(rates - expected["derivative"]) / rate_budget))
    phi = active_nodes(point.seed, proposal.after_rates.field.potential_V)
    phi_budget = 3e-13 + 3e-10 * abs(expected["potential_V"])
    errors["potential"] = float(np.max(abs(phi - expected["potential_V"]) / phi_budget))
    for key, value in proposal.transition.state.protein._asdict().items():
        target = expected["component"]["protein"][key]
        errors[key] = float(np.max(abs(value - target) / (2e-14 + 5e-13 * abs(target))))
    assert all(value <= 1 for value in errors.values())
    evidence(
        "post-ion-" + name,
        dict(
            **params,
            errors=errors,
            actual_work=actual,
            expected_work={k: expected["work"][k] for k in actual},
            energy_budget=energy_budget,
            proposal_identity=proposal.identity,
            source_point_identity=point.identity,
            split_operator_only=True,
            independently_integrated_loop=False,
            biological_cases=0,
        ),
        dict(
            actual_rates=rates,
            expected_rates=expected["derivative"],
            rate_budget=rate_budget,
            actual_phi=phi,
            expected_phi=expected["potential_V"],
            phi_budget=phi_budget,
            **{
                "actual_protein_" + k: v
                for k, v in proposal.transition.state.protein._asdict().items()
            },
            **{"expected_protein_" + k: v for k, v in expected["component"]["protein"].items()},
        ),
    )
    return expected


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("law", ("native", "stable"))
def test_post_ion_draw_work_and_complete_rates_match_independent_reference_and_replay(
    tmp_path, kind, law
):
    spec, point, preparation, _ = fixture(kind, law)
    before = fingerprints(spec, point.state, point.layout, point.component)
    proposal = propose(spec, point, preparation)
    expected = compare(kind + "-" + law, spec, point, preparation, proposal)
    budget = transition.DrivingBudget(
        expected["work"]["conditional_reversible_work_pJ"] + 1e-5,
        1e-5,
        "Synthetic declared work and dissipation; consistency test",
    )
    receipt = transition.accept(spec, proposal, budget)
    assert abs(receipt.balance_residual_pJ) <= receipt.balance_limit_pJ
    assert receipt.component.stream.next_tick == point.component.stream.next_tick + 1
    assert receipt.component.loop_calls == point.component.loop_calls + 1
    assert not receipt.admission["full_loop_checkpoint"]
    path = receipt_io.write_protein_transition(tmp_path / "receipt", spec, receipt)
    loaded = receipt_io.load_protein_transition(path)
    assert loaded.receipt.identity == receipt.identity
    assert loaded.receipt.proposal.identity == proposal.identity
    exact_tree(loaded.receipt.component.protein, receipt.component.protein)
    assert streams.stream_record(loaded.receipt.component.stream) == streams.stream_record(
        receipt.component.stream
    )
    assert fingerprints(spec, point.state, point.layout, point.component) == before


@pytest.mark.parametrize("profile", ("INIT", "fast", "dynamic_off", "protein_off", "zero_level"))
def test_original_component_guards_and_enabled_zero_draw_are_retained(profile):
    spec, point, preparation, _ = fixture(profile=profile)
    proposal = propose(spec, point, preparation)
    receipt = transition.accept(
        spec, proposal, transition.DrivingBudget(0.0, 0.0, "Declared zero-effect test")
    )
    assert (proposal.transition.packet is not None) == (profile == "zero_level")
    assert receipt.component.stream.next_tick == point.component.stream.next_tick + int(
        profile == "zero_level"
    )
    assert receipt.component.time_s == point.component.time_s + point.component.controls.dt_s
    exact_tree(receipt.component.protein, point.component.protein)


def test_two_reservoir_work_and_voltage_shift_use_separate_protein_charge_ledger():
    answers = []
    for shift in (0.0, 0.017):
        spec, point, preparation, _ = fixture("clamped", shift=shift)
        proposal = propose(spec, point, preparation)
        expected = compare("clamps-" + str(shift), spec, point, preparation, proposal)
        mask = point.layout.reservoir
        assert np.count_nonzero(mask) == 2
        independent = expected["work"]["electrode_work_pJ"]
        np.testing.assert_allclose(
            proposal.electrical.electrode_work_pJ[point.layout.outside_active],
            independent,
            atol=3e-14,
            rtol=3e-10,
        )
        assert abs(proposal.electrical.clamp_work_pJ) > 1e-8
        # Omitting the actual electrode supply must fail, even if external work
        # is otherwise chosen from the chemical and capacitor endpoints.
        missing_clamp = transition.DrivingBudget(
            proposal.thermodynamics.total_free_energy_change_pJ
            + proposal.electrical.capacitor_energy_change_pJ,
            0.0,
            "Deliberately omitted electrode work",
        )
        with pytest.raises(transition.ProteinTransitionRejected):
            transition.accept(spec, proposal, missing_clamp)
        answers.append(proposal)
    expected_shift = 1e12 * 0.017 * answers[0].electrical.gauge_work_coefficient_C
    np.testing.assert_allclose(
        answers[1].conditional_work.reversible_driving_work_pJ
        - answers[0].conditional_work.reversible_driving_work_pJ,
        expected_shift,
        atol=3e-14,
        rtol=3e-10,
    )


@pytest.mark.parametrize("kind", ("calcium", "fuel"))
def test_original_strict_family_energy_budget_cannot_be_replaced_with_passive_limit(kind):
    spec, point, preparation, _ = fixture(kind)
    proposal = propose(spec, point, preparation)
    budget = transition.DrivingBudget(
        proposal.conditional_work.reversible_driving_work_pJ + 5e-9,
        0.0,
        "Deliberate defect between strict and passive tolerances",
    )
    with pytest.raises(transition.ProteinTransitionRejected) as caught:
        transition.accept(spec, proposal, budget)
    assert caught.value.stage == "declared_work_budget"
    assert abs(caught.value.balance_residual_pJ) > 1e-9
    assert caught.value.packet is proposal.transition.packet


@pytest.mark.parametrize("defect", ("partial", "loop", "preparation", "standard"))
def test_invalid_association_refuses_before_protein_draw(defect, monkeypatch):
    spec, point, preparation, _ = fixture()
    index, standard = 0, 1.0
    if defect == "partial":
        point = replace(point, time=0.0, step_index=0, event_index=0, state=point.seed.state)
        point = held._seal(point)
    elif defect == "loop":
        index = 1
    elif defect == "preparation":
        preparation = phases.prepare(
            replace(preparation.source_state, time_s=9.0), point.binding.component
        )
    else:
        standard = -1.0

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid source consumed a protein draw")

    monkeypatch.setattr(streams, "draw", forbidden)
    with pytest.raises(transition.ProteinTransitionRejected) as caught:
        transition.propose(
            spec, point, preparation, loop_index=index, standard_concentration_mol_m3=standard
        )
    assert caught.value.packet is None


@pytest.mark.parametrize("defect", ("negative_dissipation", "nan", "bool", "missing_provenance"))
def test_invalid_drive_declarations_retain_the_proposal(defect):
    spec, point, preparation, _ = fixture()
    proposal = propose(spec, point, preparation)
    budget = transition.DrivingBudget(
        proposal.conditional_work.reversible_driving_work_pJ, 0.0, "test"
    )
    budget = replace(
        budget,
        **dict(
            negative_dissipation=dict(dissipated_free_energy_pJ=-1e-20),
            nan=dict(external_work_pJ=float("nan")),
            bool=dict(external_work_pJ=True),
            missing_provenance=dict(provenance=""),
        )[defect],
    )
    with pytest.raises(transition.ProteinTransitionRejected) as caught:
        transition.accept(spec, proposal, budget)
    assert caught.value.proposal is proposal and caught.value.packet is proposal.transition.packet


@pytest.mark.parametrize("defect", ("packet", "stream", "energy", "clock"))
def test_resealed_changed_proposals_fail_physical_or_rng_association(defect):
    spec, point, preparation, _ = fixture()
    proposal = propose(spec, point, preparation)
    changed = proposal
    if defect == "packet":
        packet = perturb.prescribed_draw(
            "protein_flux",
            point.component.stream.next_tick,
            np.full(len(point.binding.component.membrane_ids), 0.25),
            point.binding.component,
            provenance=json.loads(proposal.transition.packet.provenance_json),
        )
        changed = replace(proposal, transition=replace(proposal.transition, packet=packet))
    elif defect == "stream":
        state = replace(proposal.transition.state, stream=point.component.stream)
        changed = replace(proposal, transition=replace(proposal.transition, state=state))
    elif defect == "clock":
        state = replace(proposal.transition.state, time_s=proposal.transition.state.time_s + 1)
        changed = replace(proposal, transition=replace(proposal.transition, state=state))
    else:
        changed = replace(proposal, electrical=replace(proposal.electrical, clamp_work_pJ=1.0))
    changed = replace(changed, identity=transition.proposal_record(changed)["identity"])
    budget = transition.DrivingBudget(0.0, 0.0, "test")
    with pytest.raises(transition.ProteinTransitionRejected):
        transition.accept(spec, changed, budget)


def test_acceptance_and_saving_do_not_draw_again_and_failed_budget_can_replay(
    tmp_path, monkeypatch
):
    spec, point, preparation, _ = fixture()
    proposal = propose(spec, point, preparation)
    with pytest.raises(transition.ProteinTransitionRejected):
        transition.accept(spec, proposal, transition.DrivingBudget(10.0, 0.0, "wrong test budget"))
    repeated = propose(spec, point, preparation)
    assert repeated.identity == proposal.identity

    def forbidden(*args, **kwargs):
        pytest.fail("Acceptance/publication consumed another draw")

    monkeypatch.setattr(streams, "draw", forbidden)
    budget = transition.DrivingBudget(
        proposal.conditional_work.reversible_driving_work_pJ,
        0.0,
        "Synthetic endpoint-consistent budget, no attainability claim",
    )
    receipt = transition.accept(spec, proposal, budget)
    receipt_io.write_protein_transition(tmp_path / "receipt", spec, receipt)
    assert point.component.stream.next_tick == 31


@pytest.mark.parametrize("defect", ("partial", "bytes", "work", "loop"))
def test_receipt_corruption_and_resealed_wrong_budget_refuse(tmp_path, defect):
    spec, point, preparation, _ = fixture()
    proposal = propose(spec, point, preparation)
    receipt = transition.accept(
        spec,
        proposal,
        transition.DrivingBudget(
            proposal.conditional_work.reversible_driving_work_pJ,
            0.0,
            "Synthetic consistency fixture",
        ),
    )
    path = receipt_io.write_protein_transition(tmp_path / "receipt", spec, receipt)
    if defect == "partial":
        (path / "manifest.json").unlink()
    elif defect == "bytes":
        with (path / "receipt.json").open("a") as handle:
            handle.write("damaged")
    else:
        record = json.loads((path / "receipt.json").read_text())
        if defect == "work":
            record["budget"]["external_work_pJ"] = 1.0
        else:
            record["loop_index"] = 1
        (path / "receipt.json").write_text(json.dumps(record))
        manifest = json.loads((path / "manifest.json").read_text())
        manifest["files"] = {
            name: hashlib.sha256((path / name).read_bytes()).hexdigest()
            for name in receipt_io.FILES
        }
        manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
        (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, OSError)):
        receipt_io.load_protein_transition(path)


def test_failed_protein_material_trial_retains_packet_and_replays_without_commit():
    spec, point, preparation, _ = fixture()
    source = preparation.source_state
    source = replace(
        source,
        controls=replace(
            source.controls, dynamic_level_mol_m2_s=1e6 * source.controls.dynamic_level_mol_m2_s
        ),
    )
    preparation = phases.prepare(source, point.binding.component)
    point = held._seal(replace(point, component=preparation.held_state))
    failures = []
    for _ in range(2):
        with pytest.raises(transition.ProteinTransitionRejected) as caught:
            propose(spec, point, preparation)
        failures.append(caught.value)
        assert caught.value.stage == "post_ion_component"
        assert caught.value.packet is not None and caught.value.trial_component is not None
        assert caught.value.stream.next_tick == point.component.stream.next_tick + 1
    assert failures[0].packet.identity == failures[1].packet.identity
    assert streams.stream_record(failures[0].stream) == streams.stream_record(failures[1].stream)
    assert point.component.stream.next_tick == 31


def test_failed_receipt_publication_keeps_source_but_no_accepted_manifest(tmp_path, monkeypatch):
    spec, point, preparation, _ = fixture()
    proposal = propose(spec, point, preparation)
    receipt = transition.accept(
        spec,
        proposal,
        transition.DrivingBudget(
            proposal.conditional_work.reversible_driving_work_pJ, 0.0, "Synthetic fixture"
        ),
    )
    original = receipt_io._write_json

    def interrupted(path, value):
        if path.name == "manifest.json":
            raise OSError("injected final publication failure")
        original(path, value)

    monkeypatch.setattr(receipt_io, "_write_json", interrupted)
    with pytest.raises(OSError):
        receipt_io.write_protein_transition(tmp_path / "partial", spec, receipt)
    assert (tmp_path / "partial/source/manifest.json").is_file()
    assert not (tmp_path / "partial/manifest.json").exists()
    with pytest.raises(OSError):
        receipt_io.load_protein_transition(tmp_path / "partial")
