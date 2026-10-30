"""Complete charged calls with native blocker memory and original clocks.

Long qualification runs select individual retained round boundaries in separate
bounded processes. No numerical work runs during module import or collection.
"""

import json
import os
import platform
import shutil
import sys
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import jax
import jaxlib
import numpy as np
import pytest

from cells import physiology_protein_batch_loop_io as raw_io
from cells import physiology_protein_block_calendar_io as persistence
from cells import physiology_protein_loop_io as bare_io
from cells.core import physiology_native_calendar as clocks
from cells.core import physiology_permeability_schedule as schedules
from cells.core import physiology_protein_batch_loop as journal
from cells.core import physiology_protein_block_calendar as calls
from cells.core import physiology_protein_block_calendar_scope as scoped
from cells.core import physiology_protein_packet_provider as provider
from cells.core import physiology_random_streams as streams
from cells.core.specs import ConfigError, digest
from cells.models import physiology_block_control_view as blockers
from cells.processes import betse_global_controls as setters
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_modulated_schedule import inputs as template
from tests.integration.test_physiology_protein_charge_view import active_nodes
from tests.integration.test_physiology_protein_loop import budget
from tests.unit.test_physiology_protein_packet_provider import canonical
from tests.unit.test_physiology_tissue_step import KINDS, evidence
from validation.tissue import physiology_protein_block_calendar_reference as reference
from validation.tissue import physiology_protein_packet_provider_reference as packet_reference

HISTORIES = [
    (kind, law, phase)
    for kind in KINDS
    for law in ("native", "stable")
    for phase in ("SIM", "INIT")
] + [("clamped", law, "SIM") for law in ("native", "stable")]
ROUNDS = [(*case, index) for case in HISTORIES for index in range(2 if case[0] == "clamped" else 3)]


@pytest.fixture(scope="module", autouse=True)
def runtime_evidence():
    phase = os.environ.get("CELLS_PROTEIN_BLOCK_PHASE", "local")
    affinity = sorted(os.sched_getaffinity(0))
    declared_cpu = int(os.environ.get("CELLS_PROTEIN_BLOCK_CPU", "7"))
    if phase != "local":
        assert affinity == [declared_cpu]
    evidence(
        "protein-block-calendar-runtime-" + phase,
        dict(
            pid=os.getpid(),
            measured_child_cpu_affinity=affinity,
            declared_cpu=declared_cpu,
            python_version=platform.python_version(),
            python_full_version=sys.version,
            numpy_version=np.__version__,
            jax_version=jax.__version__,
            jaxlib_version=jaxlib.__version__,
            backend=jax.default_backend(),
            x64_enabled=bool(jax.config.x64_enabled),
            threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
            physical_solver="frozen complete charged NumPy CPU loop",
        ),
    )


@lru_cache(maxsize=32)
def initial(kind="passive", law="native", profile="normal", huge=False, enabled=True):
    spec, original, previous = template(kind, law, profile)
    component, tissue = original.initial_component, original.origin.binding
    # Caller declares the full duration before binding/conditioning. Every call
    # contains two original numerical intervals; no dt or tolerance is relaxed.
    dt = 2 * component.controls.dt_s
    component = replace(
        component,
        controls=replace(
            component.controls,
            dt_s=dt,
            dynamic_level_mol_m2_s=1e8 if huge else component.controls.dynamic_level_mol_m2_s,
        ),
    )
    calendar = clocks.bind(
        phase=component.controls.phase,
        step_count=3,
        dt_s=dt,
        provenance="Original three-call blocker/protein comparison",
    )
    plan = schedules.bind(
        spec,
        tissue,
        component,
        changes=previous.changes,
        pulses=previous.pulses,
        native_calendar=calendar,
    )
    point = calls.loop.initialise(
        spec,
        original.origin.seed,
        tissue,
        original.origin.charge_reference,
        component,
        protein_species_id=original.origin.protein_species_id,
        valence=original.origin.valence,
        standard_concentration_mol_m3=original.standard_concentration_mol_m3,
        schedule=plan,
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
            0.35 * dt,
            1.9 * dt,
            0.4 * dt,
            target_ids=tuple(name for pair in pairs.values() for name in pair),
        )
    ]
    has_pumps = any(getattr(row, "pump", None) is not None for row in spec.model.membranes)
    if has_pumps:
        events.append(setters.Event("pump_block", 0.45 * dt, 2.1 * dt, 0.5 * dt))
    program = setters.bind(
        membrane_ids=tissue.component.membrane_ids,
        events=events if enabled else (),
        provenance="Explicit paired junction and actual Na/K owners",
    )
    binding = blockers.bind(
        spec,
        tissue,
        program,
        junction_membrane_ids=pairs,
        provenance="Actual sender/receiver contact membranes",
    )
    state = blockers.BlockState(
        np.full(len(program.membrane_ids), 0.93 if enabled else 1.0),
        np.asarray(0.89 if enabled and has_pumps else 1.0),
    )
    return spec, calls.bind(spec, point, binding, state, calendar)


def no_draw(*args, **kwargs):
    raise AssertionError("Admission/restart or a refused earlier stage drew a protein packet")


def fingerprint(value):
    return journal.raw_record(journal.raw(value))


def case_name(kind, law, phase):
    return f"{kind}-{law}-{phase}"


def directory(tmp_path_factory):
    root = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    return (Path(root) if root else tmp_path_factory.getbasetemp()) / "block-calendar-snapshots"


def require(path):
    if not (path / "manifest.json").is_file():
        if os.environ.get("CELLS_PROTEIN_BLOCK_PHASE", "local") == "local":
            pytest.skip("Qualification retains each prior complete charged/block boundary")
        raise AssertionError("Required original-calendar snapshot missing: " + str(path))


def data(value):
    """Read numerical evidence as data, never execute archived Python type tags."""
    if isinstance(value, Mapping):
        if set(value) == {"type", "fields"}:
            return data(value["fields"])
        return {key: data(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(data(item) for item in value)
    return value


def archive(tmp_path, name, **values):
    root = Path(os.environ.get("CELLS_COMPONENT_EVIDENCE", str(tmp_path)))
    return persistence.write_attempt(root / "block-calendar-attempts" / name, **values)


@pytest.mark.parametrize(
    "kind,law,phase,index", ROUNDS, ids=[f"{k}-{law}-{p}-round{i}" for k, law, p, i in ROUNDS]
)
def test_complete_round_preserves_clocks_tapes_fields_ledgers_and_restart(
    tmp_path_factory,
    kind,
    law,
    phase,
    index,
):
    name = case_name(kind, law, phase)
    folder = directory(tmp_path_factory) / name
    if index == 0:
        spec, source = initial(kind, law, "INIT" if phase == "INIT" else "normal")
        persistence.write_checkpoint(folder / "origin", spec, source)
    else:
        previous = folder / ("round-" + str(index - 1))
        require(previous)
        with pytest.MonkeyPatch.context() as monkey:
            monkey.setattr(streams, "draw", no_draw)
            loaded = persistence.load_checkpoint(previous)
        spec, source = loaded.spec, loaded.checkpoint
    parent, order = fingerprint(source), []
    original_draw, original_ions = streams.draw, calls.loop.step.array_rk4_step

    def draw(*args, **kwargs):
        packet, successor = original_draw(*args, **kwargs)
        order.append("protein" if packet is not None else "protein_guard")
        return packet, successor

    def ions(*args, **kwargs):
        order.append("ions")
        return original_ions(*args, **kwargs)

    raw_folder = folder / ("raw-" + str(index))
    try:
        with pytest.MonkeyPatch.context() as monkey:
            monkey.setattr(streams, "draw", draw)
            monkey.setattr(calls.loop.step, "array_rk4_step", ions)
            proposal = calls.propose(spec, source)
    except calls.ProteinBlockRejected as error:
        persistence.write_attempt(raw_folder / "failed-proposal", source=source, failure=error)
        raise
    persistence.write_attempt(raw_folder / "proposal", source=source, proposal=proposal)
    try:
        with pytest.MonkeyPatch.context() as monkey:
            monkey.setattr(streams, "draw", no_draw)
            accepted = calls.accept(spec, source, proposal, budget(proposal.charged_proposal))
    except calls.ProteinBlockRejected as error:
        persistence.write_attempt(
            raw_folder / "failed-admission", source=source, proposal=proposal, failure=error
        )
        raise
    persistence.write_attempt(
        raw_folder / "accepted", source=source, proposal=proposal, receipt=accepted
    )
    target = accepted.checkpoint
    output = persistence.write_checkpoint(folder / ("round-" + str(index)), spec, target)
    with pytest.MonkeyPatch.context() as monkey:
        monkey.setattr(streams, "draw", no_draw)
        loaded = persistence.load_checkpoint(output)
    assert fingerprint(source) == parent
    assert calls.record(loaded.checkpoint) == calls.record(target)
    assert fingerprint(loaded.checkpoint) == fingerprint(target)
    assert target.calendar.identity == source.calendar.identity
    assert target.point.origin.identity == source.point.origin.identity
    assert target.call_index == index + 1
    assert target.point.component.loop_calls == source.point.component.loop_calls + 1
    draws = int(phase == "SIM")
    assert (
        target.point.component.stream.next_tick == source.point.component.stream.next_tick + draws
    )
    assert order == ["ions"] * len(proposal.charged_proposal.intervals) + [
        "protein" if draws else "protein_guard"
    ]
    assert len(proposal.charged_proposal.intervals) >= 2
    admission = calls.admission(accepted)
    dt = source.calendar.dt_s
    assert admission["event_label_s"] == clocks.event_label_s(source.calendar, index)
    assert admission["physical_start_s"] == index * dt
    assert admission["physical_end_s"] == (index + 1) * dt
    assert admission["declared_duration_s"] == dt
    if index:
        assert admission["event_label_s"] != admission["physical_start_s"]
    assert admission["complete_atomic_call"] and admission["original_anchors_preserved"]
    assert not admission["work_or_heat_law_inferred"]
    assert all(
        bool(row.trial.valid) and row.accounting.valid
        for row in proposal.charged_proposal.intervals
    )
    assert accepted.charged_receipt.cumulative_accounting["valid"]
    assert all(accepted.charged_receipt.cumulative_accounting["checks"].values())
    assert all(bool(value) for value in proposal.actuation["checks"].values())
    for row in proposal.interval_controls:
        np.testing.assert_array_equal(
            row["base_left"].junction,
            calls.loop.held._control(spec, float(row["start_s"])).junction,
        )
        assert not row["actual_left"].junction.flags.writeable
    if phase == "INIT":
        assert fingerprint(target.block_state) == fingerprint(source.block_state)
        assert fingerprint(target.point.component.protein) == fingerprint(
            source.point.component.protein
        )
    else:
        assert fingerprint(target.block_state) != fingerprint(source.block_state)
    assert any(
        np.any(value != 0)
        for key, value in target.point.state._asdict().items()
        if "increment" in key
    )
    if kind == "fuel":
        assert np.any(target.point.state.regeneration_supplied_work_pJ != 0)
    if kind == "clamped":
        assert np.any(proposal.charged_proposal.electrical.electrode_charge_change_C != 0)
        assert abs(float(Decimal(target.point.ledger.clamp_work_pJ))) > 1e-20
    evidence(
        "protein-block-calendar-round-" + name + "-" + str(index),
        dict(
            complete_calls=1,
            original_parent_exact=True,
            source_order=list(admission["source_order"]),
            event_label_s=admission["event_label_s"],
            elapsed_start_s=index * dt,
            elapsed_end_s=target.point.time,
            physical_subintervals=admission["physical_subintervals"],
            actual_post_ion_draws=draws,
            full_raw_attempts=str(raw_folder),
            checkpoint=str(output),
            manifest_sha256=raw_io._sha(output / "manifest.json"),
            complete_state_tape_memory_and_ledgers_exact_after_restart=True,
        ),
    )


def reference_inputs(spec, source, saved):
    point = source.point
    return dict(
        raw=spec.to_dict(),
        fields=point.state._asdict(),
        binding=calls.loop.held.units.binding_record(point.origin.binding),
        source_component=provider.source_record(point.initial_component),
        charge_reference=point.origin.charge_reference.protein._asdict(),
        block_binding=blockers.record(source.binding),
        block_state={key: value.tolist() for key, value in source.block_state._asdict().items()},
        calendar=clocks.record(source.calendar),
        start_call=source.origin_call_index,
        budgets=[row["charged_receipt"]["budget"] for row in saved],
        valence=point.origin.valence,
        standard_concentration_mol_m3=point.standard_concentration_mol_m3,
        threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
        padded_outside_capacity=point.layout.outside_active.size,
        schedule=schedules.record(point.schedule),
    )


def fraction(value, wanted, tolerance):
    return float(np.max(abs(np.asarray(value) - wanted) / tolerance, initial=0))


@pytest.mark.parametrize("kind,law,phase", HISTORIES, ids=[case_name(*case) for case in HISTORIES])
def test_independent_carried_block_ionic_protein_and_ledger_history(
    tmp_path_factory, kind, law, phase
):
    name = case_name(kind, law, phase)
    folder = directory(tmp_path_factory) / name
    count = 2 if kind == "clamped" else 3
    require(folder / ("round-" + str(count - 1)))
    original = persistence.load_checkpoint(folder / "origin")
    points = [
        persistence.load_checkpoint(folder / ("round-" + str(i))).checkpoint for i in range(count)
    ]
    saved = [
        data(raw_io.load_raw_evidence(folder / ("raw-" + str(i)) / "accepted"))[
            "speculative_receipt"
        ]
        for i in range(count)
    ]
    params = reference_inputs(original.spec, original.checkpoint, saved)
    standard, tight = reference.integrate(**params), reference.integrate(**params, refinement=2)
    record = dict(
        inputs=params,
        expected_standard=reference.report(standard),
        expected_tight=reference.report(tight),
        actual=[],
        errors=[],
        completed=False,
    )
    evidence("protein-block-calendar-reference-" + name, record)
    oracle = reference.charged.loop.ionic.local.rates.permeability.ORACLES[
        params["raw"]["model"]["id"]
    ]
    for checkpoint, receipt, target, less, control in zip(
        points,
        saved,
        tight["endpoints"],
        standard["endpoints"],
        tight["block_calls"],
        strict=True,
    ):
        proposal = receipt["charged_receipt"]["proposal"]
        context = target["context"]
        packed = oracle.flatten(context, checkpoint.point.state._asdict())
        tolerance = oracle.flatten(
            context,
            {
                key: np.full(shape, 3e-23 if key.endswith("_C") else 3e-12)
                for key, shape in context["shapes"].items()
            },
        ) + 3e-10 * abs(target["state"])
        readouts = proposal["after_rates"]["readouts"]
        field = readouts.get("field", readouts)
        phi = active_nodes(original.checkpoint.point.origin.seed, field["potential_V"])
        phi_budget = 3e-13 + 3e-10 * abs(target["potential_V"])
        errors = dict(
            state=fraction(packed, target["state"], tolerance),
            reference=fraction(less["state"], target["state"], tolerance),
            potential=fraction(phi, target["potential_V"], phi_budget),
            reference_potential=fraction(less["potential_V"], target["potential_V"], phi_budget),
        )
        for key, value in checkpoint.point.component.protein._asdict().items():
            wanted = np.asarray(target["component"]["protein"][key])
            errors["protein/" + key] = fraction(value, wanted, 2e-14 + 5e-13 * abs(wanted))
        works = dict(
            chemical_energy_change_pJ=proposal["thermodynamics"]["total_free_energy_change_pJ"],
            capacitor_energy_change_pJ=proposal["electrical"]["capacitor_energy_change_pJ"],
            clamp_work_pJ=proposal["electrical"]["clamp_work_pJ"],
        )
        for key, value in works.items():
            wanted = target["work"][key]
            errors["work/" + key] = abs(value - wanted) / (3e-14 + 3e-10 * abs(wanted))
        packet = proposal["component_transition"]["packet"]
        manifest = (
            None
            if packet is None
            else perturb.draw_manifest(
                perturb.Draw(**packet), original.checkpoint.point.origin.binding.component
            )
        )
        assert canonical(manifest) == canonical(target["packet"])
        successor = streams.stream_record(checkpoint.point.component.stream)
        assert canonical(successor) == canonical(target["successor_stream"])
        ledger = calls.loop.transition._record(checkpoint.point.ledger)
        for key in ("external_work_pJ", "dissipated_free_energy_pJ"):
            assert ledger[key] == target["ledger"][key]
        expected_clamp = float(Decimal(target["ledger"]["clamp_work_pJ"]))
        errors["ledger/clamp"] = abs(float(Decimal(ledger["clamp_work_pJ"])) - expected_clamp) / (
            3e-14 + 3e-10 * abs(expected_clamp)
        )
        expected_q = np.array([float(Decimal(v)) for v in target["ledger"]["electrode_charge_C"]])
        actual_q = np.array([float(Decimal(v)) for v in ledger["electrode_charge_C"]])
        errors["ledger/electrode"] = fraction(actual_q, expected_q, 3e-25 + 2e-12 * abs(expected_q))
        cumulative = receipt["charged_receipt"]["cumulative_accounting"]
        wanted = target["global_accounting"]["energy_residual_pJ"]
        errors["cumulative_energy"] = abs(cumulative["energy_residual_pJ"] - wanted) / (
            3e-14 + 3e-10 * abs(wanted)
        )
        for key, value in checkpoint.block_state._asdict().items():
            errors["block_memory/" + key] = fraction(
                value, np.asarray(control["block_state"][key]), 3e-15 + 3e-14 * abs(value)
            )
        for actual_control, expected_control in zip(
            receipt["proposal"]["interval_controls"], control["interval_controls"], strict=True
        ):
            for side in ("base_left", "base_right", "actual_left", "actual_right"):
                for key, value in actual_control[side].items():
                    wanted = np.asarray(expected_control[side][key])
                    errors["controls/" + side + "/" + key] = max(
                        errors.get("controls/" + side + "/" + key, 0),
                        fraction(value, wanted, 3e-15 + 3e-14 * abs(wanted)),
                    )
        record["actual"].append(
            dict(
                state=packed,
                full_fields=checkpoint.point.state._asdict(),
                state_budget=tolerance,
                potential_V=phi,
                potential_budget=phi_budget,
                protein=checkpoint.point.component.protein._asdict(),
                work=works,
                packet=manifest,
                successor_stream=successor,
                ledger=ledger,
                cumulative=cumulative,
                block_state=checkpoint.block_state._asdict(),
                interval_controls=receipt["proposal"]["interval_controls"],
            )
        )
        record["errors"].append(errors)
        evidence("protein-block-calendar-reference-" + name, record)
        assert cumulative["valid"] and all(cumulative["checks"].values())
        assert target["global_accounting"]["energy_valid"]
        assert max(errors["reference"], errors["reference_potential"]) <= 0.1
    record.update(
        completed=True, maximum_error_fraction=max(max(row.values()) for row in record["errors"])
    )
    evidence("protein-block-calendar-reference-" + name, record)
    assert record["maximum_error_fraction"] <= 1, record["errors"]


@lru_cache(maxsize=4)
def first(law="native"):
    spec, source = initial(law=law)
    proposal = calls.propose(spec, source)
    return spec, source, calls.accept(spec, source, proposal, budget(proposal.charged_proposal))


@pytest.mark.parametrize("law", ("native", "stable"))
def test_unblocked_composition_matches_original_complete_charged_loop(law):
    spec, source = initial(law=law, enabled=False)
    bare = calls.loop.propose(spec, source.point)
    controlled = calls.propose(spec, source)
    assert calls.loop.proposal_record(bare) == calls.loop.proposal_record(
        controlled.charged_proposal
    )
    declaration = budget(bare)
    target = calls.accept(spec, source, controlled, declaration)
    original = calls.loop.accept(spec, source.point, bare, declaration)
    assert calls.loop.checkpoint_record(target.checkpoint.point) == calls.loop.checkpoint_record(
        original.checkpoint
    )
    assert target.charged_receipt.identity == original.identity


@pytest.mark.parametrize("law", ("native", "stable"))
@pytest.mark.parametrize("profile", ("fast", "dynamic_off", "protein_off", "zero_level"))
def test_original_random_guards_preserve_complete_ionic_evolution(law, profile):
    spec, source = initial(law=law, profile=profile)
    proposal = calls.propose(spec, source)
    target = calls.accept(spec, source, proposal, budget(proposal.charged_proposal)).checkpoint
    draws = int(profile == "zero_level")
    assert (proposal.charged_proposal.component_transition.packet is not None) == bool(draws)
    assert (
        target.point.component.stream.next_tick == source.point.component.stream.next_tick + draws
    )
    assert target.point.component.loop_calls == source.point.component.loop_calls + 1
    assert fingerprint(target.point.component.protein) == fingerprint(
        source.point.component.protein
    )
    assert fingerprint(target.point.state) != fingerprint(source.point.state)
    assert fingerprint(target.block_state) != fingerprint(source.block_state)


def test_private_scopes_reuse_frozen_code_without_mutating_shared_globals(monkeypatch):
    spec, source = initial()
    old_held, old_actual, old_endpoints = (
        calls.loop.held,
        calls.loop._actual,
        calls.loop.transition._endpoints,
    )
    context, other = calls.scope(spec, source), calls.scope(spec, source)
    assert context.codec.KIND == scoped.INNER_KIND
    assert context.codec.SCHEDULED_KIND == scoped.INNER_SCHEDULED_KIND
    with monkeypatch.context() as local:
        local.setattr(streams, "draw", no_draw)
        bound, preparation = context.proposal_loop(0)
        assert bound.propose.__code__ is calls.loop.propose.__code__
        assert bound.accept.__code__ is calls.loop.accept.__code__
        assert bound._ions.__code__ is calls.loop._ions.__code__
        assert bound.transition._endpoints.__code__ is old_endpoints.__code__
        assert (
            context.codec.load_protein_loop_checkpoint.__code__
            is bare_io.load_protein_loop_checkpoint.__code__
        )
        assert context.validation.validate.__globals__ is not other.validation.validate.__globals__
        assert bound.validate is context.validation.validate
        assert fingerprint(preparation) == fingerprint(context.stage(0))
    assert calls.loop.held is old_held and calls.loop._actual is old_actual
    assert calls.loop.transition._endpoints is old_endpoints


def test_explicit_full_call_replay_preserves_exact_control_and_receipt_association():
    spec, source, accepted = first()
    target = persistence.replay(spec, source, (accepted,))
    assert fingerprint(target) == fingerprint(accepted.checkpoint)
    assert target.calendar.identity == source.calendar.identity


def test_existing_destination_refuses_before_loading_or_advancing(tmp_path, monkeypatch):
    destination = tmp_path / "exists"
    destination.mkdir()
    monkeypatch.setattr(persistence, "load_checkpoint", no_draw)
    with pytest.raises(FileExistsError):
        persistence.advance_checkpoint(tmp_path / "unused", destination, None)


@pytest.mark.parametrize(
    "defect", ("calendar", "phase", "cursor", "memory", "initial_memory", "owner", "bare_history")
)
def test_resealed_checkpoint_context_changes_refuse(defect):
    spec, source, accepted = first()
    bad = accepted.checkpoint
    if defect == "calendar":
        bad = replace(
            bad,
            calendar=clocks.bind(
                phase="SIM",
                step_count=2,
                dt_s=source.calendar.dt_s,
                provenance="Rebased remaining window",
            ),
        )
    elif defect == "phase":
        bad = replace(
            bad,
            calendar=clocks.bind(
                phase="INIT", step_count=3, dt_s=source.calendar.dt_s, provenance="Wrong phase"
            ),
        )
    elif defect == "cursor":
        bad = replace(bad, call_index=2)
    elif defect == "memory":
        bad = replace(
            bad,
            block_state=bad.block_state._replace(
                junction_available=np.ones_like(bad.block_state.junction_available)
            ),
        )
    elif defect == "initial_memory":
        bad = replace(
            bad,
            initial_block_state=bad.initial_block_state._replace(
                junction_available=np.ones_like(bad.initial_block_state.junction_available)
            ),
        )
    elif defect == "owner":
        bad = replace(bad, binding=replace(bad.binding, tissue_binding_identity="0" * 64))
    else:
        with pytest.raises(ValueError, match="original charged boundary"):
            calls.bind(spec, bad.point, bad.binding, bad.block_state, bad.calendar)
        return
    bad = calls._seal(bad)
    with pytest.raises((ValueError, calls.ProteinBlockRejected)):
        calls.validate(spec, bad)
    assert source.call_index == 0


@pytest.mark.parametrize(
    "defect", ("parent", "preparation", "controls", "ionic_trial", "packet", "successor")
)
def test_resealed_proposals_refuse_without_advancing_any_parent(tmp_path, defect, monkeypatch):
    spec, source, accepted = first()
    proposal = accepted.proposal
    original = fingerprint(source)
    if defect == "parent":
        source = accepted.checkpoint
        original = fingerprint(source)
    elif defect == "preparation":
        proposal = replace(proposal, preparation=proposal.preparation._replace(event_time_s=0.5))
    elif defect == "controls":
        row = proposal.interval_controls[0]
        changed = row | dict(
            actual_left=row["actual_left"]._replace(junction=row["actual_left"].junction * 0.5)
        )
        proposal = replace(proposal, interval_controls=(changed, *proposal.interval_controls[1:]))
    else:
        charged = proposal.charged_proposal
        if defect == "ionic_trial":
            row = charged.intervals[-1]
            state = row.trial.proposed_state
            changed = state._replace(amount_increment=state.amount_increment + 1e-3)
            charged = replace(
                charged,
                intervals=(
                    *charged.intervals[:-1],
                    replace(row, trial=row.trial._replace(proposed_state=changed)),
                ),
            )
        elif defect == "packet":
            charged = replace(
                charged, component_transition=replace(charged.component_transition, packet=None)
            )
        else:
            changed = replace(
                charged.component_transition.state, stream=source.point.component.stream
            )
            charged = replace(
                charged, component_transition=replace(charged.component_transition, state=changed)
            )
        charged = replace(charged, identity=calls.loop.proposal_record(charged)["identity"])
        proposal = replace(proposal, charged_proposal=charged)
    proposal = replace(proposal, identity=calls.proposal_record(proposal)["identity"])
    monkeypatch.setattr(streams, "draw", no_draw)
    with pytest.raises(calls.ProteinBlockRejected) as caught:
        calls.accept(spec, source, proposal, accepted.charged_receipt.budget)
    archive(tmp_path, "resealed-" + defect, source=source, proposal=proposal, failure=caught.value)
    assert caught.value.source is source and fingerprint(source) == original


@pytest.mark.parametrize("law", ("native", "stable"))
def test_real_failed_protein_packet_successor_and_all_ionic_trials_are_retained(tmp_path, law):
    spec, source = initial(law=law, huge=True)
    original = fingerprint(source)
    with pytest.raises(calls.ProteinBlockRejected) as caught:
        calls.propose(spec, source)
    failure = caught.value
    output = archive(tmp_path, "real-protein-failure-" + law, source=source, failure=failure)
    assert fingerprint(source) == original and failure.source is source
    assert failure.packet is not None and failure.stream is not None
    assert len(failure.intervals) >= 2 and failure.trial is not None
    assert failure.stream.next_tick == source.point.component.stream.next_tick + 1
    staged = failure.failure.preparation.source_state
    params = dict(
        binding=calls.loop.held.units.binding_record(source.point.origin.binding),
        source=provider.source_record(staged),
        threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
    )
    expected = packet_reference.provide(**params)
    actual_packet = perturb.draw_manifest(failure.packet, source.point.origin.binding.component)
    assert canonical(actual_packet) == canonical(expected["packet"])
    assert canonical(streams.stream_record(failure.stream)) == canonical(
        expected["successor_stream"]
    )
    evidence(
        "protein-block-calendar-failed-provider-" + law,
        dict(
            inputs=params,
            expected=expected,
            actual_packet=actual_packet,
            actual_successor=streams.stream_record(failure.stream),
            actual_failure_archive=str(output),
            actual_failure_manifest_sha256=raw_io._sha(output / "manifest.json"),
        ),
    )


def test_failed_ionic_trial_keeps_nonfinite_numeric_evidence_and_does_not_draw(
    tmp_path, monkeypatch
):
    spec, source = initial()
    original, rk4 = fingerprint(source), calls.loop.step.array_rk4_step

    def failed(*args, **kwargs):
        trial = rk4(*args, **kwargs)
        state = trial.proposed_state
        values = np.array(state.amount_increment, copy=True)
        values.flat[0] = np.nan
        return trial._replace(
            proposed_state=state._replace(amount_increment=values), valid=np.asarray(False)
        )

    monkeypatch.setattr(streams, "draw", no_draw)
    monkeypatch.setattr(calls.loop.step, "array_rk4_step", failed)
    with pytest.raises(calls.ProteinBlockRejected) as caught:
        calls.propose(spec, source)
    failure = caught.value
    output = archive(tmp_path, "actual-nonfinite-ionic", source=source, failure=failure)
    restored = raw_io.load_raw_evidence(output)
    assert journal.raw_record(journal.raw(failure.trial)) == journal.raw_record(
        restored["failure"]["fields"]["trial"]
    )
    assert np.isnan(failure.trial.proposed_state.amount_increment).any()
    assert failure.packet is None and fingerprint(source) == original


@pytest.mark.parametrize("kind", ("passive", "fuel"))
def test_local_errors_cannot_accumulate_a_larger_global_limit(tmp_path, kind):
    spec, source = initial(kind)
    before = fingerprint(source)
    proposal = calls.propose(spec, source)
    context = calls.validate(spec, source)
    limit = context.validation.validate(spec, source.point)["energy_limit_pJ"]
    with pytest.raises(calls.ProteinBlockRejected) as caught:
        calls.accept(spec, source, proposal, budget(proposal.charged_proposal, offset=8 * limit))
    archive(
        tmp_path, "local-budget-" + kind, source=source, proposal=proposal, failure=caught.value
    )
    assert fingerprint(source) == before
    one = calls.accept(
        spec, source, proposal, budget(proposal.charged_proposal, offset=0.6 * limit)
    )
    again = calls.propose(spec, one.checkpoint)
    parent = fingerprint(one.checkpoint)
    with pytest.raises(calls.ProteinBlockRejected) as caught:
        calls.accept(
            spec, one.checkpoint, again, budget(again.charged_proposal, offset=0.6 * limit)
        )
    archive(
        tmp_path,
        "cumulative-budget-" + kind,
        source=one.checkpoint,
        proposal=again,
        failure=caught.value,
    )
    assert caught.value.failure.stage == "cumulative_accounting"
    assert abs(caught.value.failure.report["energy_residual_pJ"]) > limit
    assert fingerprint(one.checkpoint) == parent


@pytest.mark.parametrize("kind", ("temperature", "voltage", "pump_block"))
def test_unsupported_setters_and_absent_pump_owners_refuse(kind):
    spec, source = initial()
    options = (
        dict(amplitude=0.1, positive_boundary="top", negative_boundary="bottom")
        if kind == "voltage"
        else {}
    )
    program = setters.bind(
        membrane_ids=source.binding.program.membrane_ids,
        events=(setters.Event(kind, 0.2, 1.2, 0.3, **options),),
        provenance="Explicit unsupported source setter",
    )
    with pytest.raises(ValueError):
        blockers.bind(
            spec,
            source.point.origin.binding,
            program,
            junction_membrane_ids={j: (a, b) for j, a, b in source.binding.junction_membranes},
            provenance=source.binding.provenance,
        )


def test_asymmetric_contact_refuses_before_any_ionic_evolution_or_packet(tmp_path, monkeypatch):
    spec, source = initial()
    old = source.binding
    program = setters.bind(
        membrane_ids=old.program.membrane_ids,
        events=(replace(old.program.events[0], target_ids=(old.junction_membranes[0][1],)),),
        provenance=old.program.provenance,
    )
    binding = blockers.bind(
        spec,
        source.point.origin.binding,
        program,
        junction_membrane_ids={j: (a, b) for j, a, b in old.junction_membranes},
        provenance=old.provenance,
    )
    source = calls.bind(spec, source.point, binding, source.initial_block_state, source.calendar)
    before = fingerprint(source)
    monkeypatch.setattr(streams, "draw", no_draw)
    monkeypatch.setattr(calls.loop.step, "array_rk4_step", no_draw)
    with pytest.raises(calls.ProteinBlockRejected) as caught:
        calls.propose(spec, source)
    archive(tmp_path, "asymmetric-contact", source=source, failure=caught.value)
    assert caught.value.stage == "native_block_preparation"
    assert caught.value.trial is not None and fingerprint(source) == before


@pytest.mark.parametrize(
    "defect", ("bare_loader", "metadata", "numeric_memory", "missing_field", "source_runtime")
)
def test_restart_requires_entire_original_block_context(tmp_path, defect, monkeypatch):
    spec, _, accepted = first()
    source = accepted.checkpoint
    original = persistence.write_checkpoint(tmp_path / "original", spec, source)
    target = tmp_path / "changed"
    shutil.copytree(original, target)
    monkeypatch.setattr(streams, "draw", no_draw)
    if defect == "bare_loader":
        with pytest.raises(ConfigError):
            bare_io.load_protein_loop_checkpoint(target / "charged")
        assert persistence.load_checkpoint(original).checkpoint.identity == source.identity
        return
    manifest = json.loads((target / "manifest.json").read_text())
    if defect == "metadata":
        record = json.loads((target / "block-context.json").read_text())
        record["origin_call_index"] = 1
        (target / "block-context.json").write_text(json.dumps(record))
        manifest["files"]["block-context.json"] = raw_io._sha(target / "block-context.json")
    elif defect in ("numeric_memory", "missing_field"):
        with np.load(target / "block-state.npz", allow_pickle=False) as saved:
            arrays = {name: saved[name] for name in saved.files}
        if defect == "numeric_memory":
            arrays["current/junction_available"] = np.ones_like(
                arrays["current/junction_available"]
            )
        else:
            del arrays["initial/pump_available"]
        np.savez(target / "block-state.npz", **arrays)
        manifest["files"]["block-state.npz"] = raw_io._sha(target / "block-state.npz")
    else:
        manifest["runtime"]["backend"] = "gpu"
    manifest["identity"] = digest({k: v for k, v in manifest.items() if k != "identity"})
    (target / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises((ValueError, ConfigError, calls.ProteinBlockRejected)):
        persistence.load_checkpoint(target)
    assert persistence.load_checkpoint(original).checkpoint.identity == source.identity


def test_terminal_calendar_refuses_and_keeps_original_full_phase(tmp_path_factory, monkeypatch):
    folder = directory(tmp_path_factory) / "passive-native-SIM" / "round-2"
    require(folder)
    source = persistence.load_checkpoint(folder)
    before = fingerprint(source.checkpoint)
    monkeypatch.setattr(streams, "draw", no_draw)
    monkeypatch.setattr(calls.loop.step, "array_rk4_step", no_draw)
    with pytest.raises(calls.ProteinBlockRejected) as caught:
        calls.propose(source.spec, source.checkpoint)
    assert caught.value.stage == "native_block_preparation"
    assert source.checkpoint.calendar.step_count == 3
    assert source.checkpoint.call_index == 3 and fingerprint(source.checkpoint) == before
