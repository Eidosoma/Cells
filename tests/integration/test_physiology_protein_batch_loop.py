"""Complete charged cohorts, per-world ledgers, real tapes and durable history."""

import json
import os
import platform
import sys
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import jax
import jaxlib
import numpy as np
import pytest

from cells import physiology_protein_batch_loop_io as persistence
from cells.core import physiology_permeability_schedule as schedules
from cells.core import physiology_protein_batch_loop as batch
from cells.core import physiology_protein_packet_provider as provider
from cells.core import physiology_random_streams as streams
from cells.core.specs import ConfigError
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_modulated_schedule import inputs as template
from tests.integration.test_physiology_protein_charge_view import active_nodes
from tests.integration.test_physiology_protein_loop import budget, loop_input
from tests.unit.test_physiology_protein_packet_provider import canonical
from tests.unit.test_physiology_tissue_step import KINDS, evidence
from validation.tissue import physiology_protein_batch_loop_reference as reference
from validation.tissue import physiology_protein_packet_provider_reference as packet_reference


@pytest.fixture(scope="module", autouse=True)
def runtime_evidence():
    phase = os.environ.get("CELLS_PROTEIN_BATCH_PHASE", "local")
    affinity = sorted(os.sched_getaffinity(0))
    if phase != "local":
        assert affinity == [7]
    evidence(
        "protein-batch-loop-runtime-" + phase,
        dict(
            pid=os.getpid(),
            measured_child_cpu_affinity=affinity,
            python_version=platform.python_version(),
            python_full_version=sys.version,
            numpy_version=np.__version__,
            jax_version=jax.__version__,
            jaxlib_version=jaxlib.__version__,
            backend=jax.default_backend(),
            x64_enabled=bool(jax.config.x64_enabled),
            threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
            physical_solver="frozen complete charged loop; NumPy CPU",
        ),
    )


@lru_cache(maxsize=80)
def world(
    kind="passive",
    law="native",
    profile="normal",
    *,
    label="world",
    index=101,
    native_tape=0,
    terminal=None,
    huge=False,
):
    spec, original, previous = template(kind, law, profile)
    component, binding = original.initial_component, original.origin.binding
    rng = component.stream.rng
    if type(rng) is perturb.NativeStream:
        # Caller-declared fixture tapes, independent of all world names/IDs.
        state = np.random.RandomState((17, 83, 109, 271)[native_tape])
        state.normal()
        rng = perturb._native_stream(state.get_state(), np.__version__)
    else:
        rng = perturb.StableCoordinates(rng.seed, 2**40 + index)
    stream = streams.new_stream(
        binding.component,
        rng,
        stream_id=component.stream.stream_id,
        world_id=2**40 + index,
        next_tick=2**64 - 2 if terminal == "tick" else component.stream.next_tick,
    )
    component = replace(
        component,
        stream=stream,
        loop_calls=2**64 - 2 if terminal == "calls" else component.loop_calls,
    )
    if huge:
        component = replace(
            component, controls=replace(component.controls, dynamic_level_mol_m2_s=1e8)
        )
    plan = schedules.bind(
        spec,
        binding,
        component,
        changes=previous.changes,
        pulses=previous.pulses,
        native_calendar=previous.native_calendar,
    )
    point = batch.loop.initialise(
        spec,
        original.origin.seed,
        binding,
        original.origin.charge_reference,
        component,
        protein_species_id=original.origin.protein_species_id,
        valence=original.origin.valence,
        standard_concentration_mol_m3=original.standard_concentration_mol_m3,
        schedule=plan,
    )
    return batch.initialise_world(label, spec, point)


def declared(_world, proposal):
    # Explicit manufactured consistency declaration supplied by this test.
    # Production batch code has no default physical work/heat model.
    return budget(proposal)


def no_draw(*args, **kwargs):
    raise AssertionError("Acceptance and restore must never draw another packet")


def fingerprint(value):
    return batch.raw_record(batch.raw(value))


def reference_inputs(source, receipts):
    point, spec = source.base, source.spec
    return dict(
        raw=spec.to_dict(),
        fields=point.state._asdict(),
        binding=batch.loop.held.units.binding_record(point.origin.binding),
        source_component=provider.source_record(point.initial_component),
        charge_reference=point.origin.charge_reference.protein._asdict(),
        loops=[
            loop_input(spec, receipt.proposal)
            | dict(
                loop_index=receipt.checkpoint.loop_index - 1,
                budget=batch.loop.transition._record(receipt.budget),
            )
            for receipt in receipts
        ],
        valence=point.origin.valence,
        standard_concentration_mol_m3=point.standard_concentration_mol_m3,
        threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
        padded_outside_capacity=point.layout.outside_active.size,
        schedule=schedules.record(point.schedule),
    )


def compare_reference(name, source, receipts):
    inputs = reference_inputs(source, receipts)
    standard = reference.integrate(**inputs)
    tight = reference.integrate(**inputs, refinement=2)
    rows, actual = [], []
    record = dict(
        inputs=inputs,
        expected_standard=reference.report(standard),
        expected_tight=reference.report(tight),
        actual=actual,
        errors=rows,
        completed=False,
        independent_complete_history=True,
        independent_rng_engine=True,
    )
    evidence("protein-batch-loop-reference-" + name, record)
    oracle = reference.loop.ionic.local.rates.permeability.ORACLES[inputs["raw"]["model"]["id"]]
    for receipt, target, less in zip(
        receipts, tight["endpoints"], standard["endpoints"], strict=True
    ):
        context = target["context"]
        values = oracle.flatten(context, receipt.checkpoint.state._asdict())
        tolerance = oracle.flatten(
            context,
            {
                field: np.full(shape, 3e-23 if field.endswith("_C") else 3e-12)
                for field, shape in context["shapes"].items()
            },
        ) + 3e-10 * abs(target["state"])
        phi = active_nodes(source.base.origin.seed, receipt.proposal.after_rates.field.potential_V)
        ptol = 3e-13 + 3e-10 * abs(target["potential_V"])
        errors = dict(
            state=float(np.max(abs(values - target["state"]) / tolerance)),
            reference=float(np.max(abs(less["state"] - target["state"]) / tolerance)),
            potential=float(np.max(abs(phi - target["potential_V"]) / ptol)),
            reference_potential=float(
                np.max(abs(less["potential_V"] - target["potential_V"]) / ptol)
            ),
        )
        for field, value in receipt.checkpoint.component.protein._asdict().items():
            expected = np.asarray(target["component"]["protein"][field])
            errors["protein/" + field] = float(
                np.max(abs(value - expected) / (2e-14 + 5e-13 * abs(expected)))
            )
        works = dict(
            chemical_energy_change_pJ=receipt.proposal.thermodynamics.total_free_energy_change_pJ,
            capacitor_energy_change_pJ=receipt.proposal.electrical.capacitor_energy_change_pJ,
            clamp_work_pJ=receipt.proposal.electrical.clamp_work_pJ,
        )
        for field, value in works.items():
            expected = target["work"][field]
            errors["work/" + field] = abs(value - expected) / (3e-14 + 3e-10 * abs(expected))
        packet = receipt.proposal.component_transition.packet
        manifest = (
            None
            if packet is None
            else perturb.draw_manifest(packet, source.base.origin.binding.component)
        )
        assert canonical(manifest) == canonical(target["packet"])
        assert canonical(streams.stream_record(receipt.checkpoint.component.stream)) == canonical(
            target["successor_stream"]
        )
        for field in ("external_work_pJ", "dissipated_free_energy_pJ"):
            assert getattr(receipt.checkpoint.ledger, field) == target["ledger"][field]
        clamp = float(Decimal(receipt.checkpoint.ledger.clamp_work_pJ))
        expected_clamp = float(Decimal(target["ledger"]["clamp_work_pJ"]))
        errors["ledger/clamp"] = abs(clamp - expected_clamp) / (3e-14 + 3e-10 * abs(expected_clamp))
        q = np.array([float(Decimal(v)) for v in receipt.checkpoint.ledger.electrode_charge_C])
        expected_q = np.array([float(Decimal(v)) for v in target["ledger"]["electrode_charge_C"]])
        errors["ledger/electrode"] = float(
            np.max(abs(q - expected_q) / (3e-25 + 2e-12 * abs(expected_q)))
        )
        global_target = target["global_accounting"]["energy_residual_pJ"]
        errors["cumulative_energy"] = abs(
            receipt.cumulative_accounting["energy_residual_pJ"] - global_target
        ) / (3e-14 + 3e-10 * abs(global_target))
        rows.append(errors)
        actual.append(
            dict(
                state=values,
                full_fields=receipt.checkpoint.state._asdict(),
                potential_V=phi,
                protein=receipt.checkpoint.component.protein._asdict(),
                work=works,
                packet=manifest,
                successor_stream=streams.stream_record(receipt.checkpoint.component.stream),
                ledger=batch.loop.transition._record(receipt.checkpoint.ledger),
                cumulative=batch.loop.transition._record(receipt.cumulative_accounting),
                state_budget=tolerance,
                potential_budget=ptol,
            )
        )
        evidence("protein-batch-loop-reference-" + name, record)
        assert target["global_accounting"]["energy_valid"]
        assert receipt.cumulative_accounting["valid"]
        assert all(receipt.cumulative_accounting["checks"].values())
        assert max(errors["reference"], errors["reference_potential"]) <= 0.1
    evidence(
        "protein-batch-loop-reference-" + name,
        dict(
            inputs=inputs,
            expected_standard=reference.report(standard),
            expected_tight=reference.report(tight),
            actual=actual,
            errors=rows,
            maximum_error_fraction=max(max(row.values()) for row in rows),
            independent_complete_history=True,
            independent_rng_engine=True,
            completed=True,
        ),
    )
    assert all(max(row.values()) <= 1 for row in rows), rows


COUPLED_CASES = [
    (kind, law, 2 if kind == "clamped" else 3)
    for kind in (*KINDS, "clamped")
    for law in ("native", "stable")
]
PROFILES = ("normal", "dynamic_off", "zero_level")
ROUND_CASES = [(kind, law, index) for kind, law, count in COUPLED_CASES for index in range(count)]
REFERENCE_CASES = [(kind, law, profile) for kind, law, _ in COUPLED_CASES for profile in PROFILES]


def snapshots(tmp_path_factory):
    base = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    return (Path(base) if base else tmp_path_factory.getbasetemp()) / "batch-snapshots"


def round_path(tmp_path_factory, kind, law, index):
    return snapshots(tmp_path_factory) / (kind + "-" + law) / ("round-" + str(index))


def require_snapshot(path):
    if not (path / "manifest.json").is_file():
        if os.environ.get("CELLS_PROTEIN_BATCH_PHASE", "local") == "local":
            pytest.skip("Complete-round qualification supplies retained whole-world checkpoints")
        raise AssertionError("Required prior complete-round snapshot is missing: " + str(path))


def unwrapped(value):
    # Read the preserved raw journal as data; never import/execute its type tags.
    if isinstance(value, Mapping):
        if set(value) == {"type", "fields"}:
            return unwrapped(value["fields"])
        return {key: unwrapped(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(unwrapped(item) for item in value)
    return value


def recorded_receipts(saved):
    receipts = []
    for index, entry in enumerate(saved.history):
        record = unwrapped(entry.payload["speculative_receipt"])
        p = record["proposal"]
        packet = p["component_transition"]["packet"]
        packet = None if packet is None else perturb.Draw(**packet)
        readouts = p["after_rates"]["readouts"]
        field = readouts["field"] if "field" in readouts else readouts
        point = (
            saved.history[index + 1].source if index + 1 < len(saved.history) else saved.checkpoint
        )
        proposal = SimpleNamespace(
            identity=entry.proposal_identity,
            component_transition=SimpleNamespace(packet=packet),
            intervals=tuple(
                SimpleNamespace(start_s=row["start_s"], end_s=row["end_s"])
                for row in p["intervals"]
            ),
            after_rates=SimpleNamespace(field=SimpleNamespace(potential_V=field["potential_V"])),
            thermodynamics=SimpleNamespace(**p["thermodynamics"]),
            electrical=SimpleNamespace(**p["electrical"]),
        )
        receipts.append(
            SimpleNamespace(
                checkpoint=point,
                proposal=proposal,
                budget=entry.budget,
                cumulative_accounting=record["cumulative_accounting"],
                identity=entry.receipt_identity,
            )
        )
    return receipts


@pytest.mark.parametrize(
    "kind,law,round_index", ROUND_CASES, ids=[f"{k}-{law}-round{i}" for k, law, i in ROUND_CASES]
)
def test_complete_world_round_preserves_physics_tapes_calendars_and_restart(
    tmp_path_factory, kind, law, round_index
):
    if round_index == 0:
        sources = tuple(
            world(kind, law, profile, label=profile, index=101 + i, native_tape=i)
            for i, profile in enumerate(PROFILES)
        )
    else:
        previous = round_path(tmp_path_factory, kind, law, round_index - 1)
        require_snapshot(previous)
        with pytest.MonkeyPatch.context() as m:
            m.setattr(streams, "draw", no_draw)
            sources = persistence.load_batch_checkpoint(previous).worlds
    before = [fingerprint(w.checkpoint) for w in sources]
    proposed = batch.propose_batch(sources)
    raw_folder = (
        snapshots(tmp_path_factory).parent / "batch-raw" / f"{kind}-{law}-round{round_index}"
    )
    for index, row in enumerate(proposed.worlds):
        persistence.write_raw_evidence(
            raw_folder / f"proposed-{index}",
            batch.raw(
                dict(
                    source_checkpoint=row.source.checkpoint,
                    proposal=row.proposal,
                    failure=row.failure,
                )
            ),
        )
    assert all(row.failure is None for row in proposed.worlds), [
        str(row.failure) for row in proposed.worlds
    ]
    budgets = {row.source.world_id: declared(row.source, row.proposal) for row in proposed.worlds}
    with pytest.MonkeyPatch.context() as m:
        m.setattr(streams, "draw", no_draw)
        result = batch.accept_batch(sources, proposed, budgets)
    for index, attempt in enumerate(result.attempts):
        persistence.write_raw_evidence(raw_folder / f"attempted-{index}", attempt.payload)
    assert result.valid.tolist() == [True] * 3, [str(a.failure) for a in result.attempts]
    output = round_path(tmp_path_factory, kind, law, round_index)
    persistence.write_batch_checkpoint(output, result.worlds, attempts=result.attempts)
    with pytest.MonkeyPatch.context() as m:
        m.setattr(streams, "draw", no_draw)
        restored = persistence.load_batch_checkpoint(output)
    for source, target, loaded, attempt, original in zip(
        sources, result.worlds, restored.worlds, result.attempts, before, strict=True
    ):
        assert fingerprint(source.checkpoint) == original
        assert batch.world_record(target) == batch.world_record(loaded)
        assert len(target.history) == round_index + 1
        assert target.checkpoint.component.loop_calls == source.checkpoint.component.loop_calls + 1
        draws = int(source.world_id != "dynamic_off")
        assert (
            target.checkpoint.component.stream.next_tick
            == source.checkpoint.component.stream.next_tick + draws
        )
        assert (
            target.checkpoint.schedule.native_calendar.identity
            == source.checkpoint.schedule.native_calendar.identity
        )
        proposal = attempt.proposal
        dt = source.checkpoint.component.controls.dt_s
        staging = proposal.permeability_staging
        assert staging["sampled_time_s"] == schedules.sample_time_s(
            source.checkpoint.schedule, round_index
        )
        assert staging["nominal_start_s"] == round_index * dt
        assert staging["nominal_duration_s"] == dt
        assert proposal.intervals[0].start_s == round_index * dt
        assert proposal.intervals[-1].end_s == (round_index + 1) * dt
        assert all(row.trial.valid and row.accounting.valid for row in proposal.intervals)
        assert attempt.component_commit.valid.tolist() == [True]
        assert attempt.receipt.cumulative_accounting["valid"]
    if kind == "fuel":
        assert np.any(result.worlds[0].checkpoint.state.energy_amount_increment_fmol != 0)
        assert np.any(result.worlds[0].checkpoint.state.regeneration_supplied_work_pJ != 0)
    if kind == "clamped":
        assert any(
            abs(float(Decimal(w.checkpoint.ledger.clamp_work_pJ))) > 1e-20 for w in result.worlds
        )
    evidence(
        f"protein-batch-loop-round-{kind}-{law}-{round_index}",
        dict(
            worlds=3,
            complete_loops=3,
            checkpoint=str(output),
            manifest_sha256=persistence._sha(output / "manifest.json"),
            original_parents_exact=True,
            restart_without_draw=True,
            native_calendar_preserved=True,
            full_raw_ionic_and_component_attempts=True,
            whole_world_identities=[w.identity for w in result.worlds],
        ),
    )


@pytest.mark.parametrize(
    "kind,law,profile", REFERENCE_CASES, ids=[f"{k}-{law}-{p}" for k, law, p in REFERENCE_CASES]
)
def test_carried_complete_world_matches_serial_and_independent_full_history(
    tmp_path_factory, kind, law, profile
):
    count = 2 if kind == "clamped" else 3
    output = round_path(tmp_path_factory, kind, law, count - 1)
    require_snapshot(output)
    snapshot = persistence.load_batch_checkpoint(output)
    saved = next(w for w in snapshot.worlds if w.world_id == profile)
    source = batch.initialise_world(saved.world_id, saved.spec, saved.base)
    receipts = recorded_receipts(saved)
    serial = saved.base
    for receipt in receipts:
        proposal = batch.loop.propose(saved.spec, serial)
        accepted = batch.loop.accept(saved.spec, serial, proposal, declared(source, proposal))
        raw_folder = snapshots(tmp_path_factory).parent / "batch-serial" / f"{kind}-{law}-{profile}"
        persistence.write_raw_evidence(
            raw_folder / str(serial.loop_index),
            batch.raw(
                dict(
                    source_checkpoint=serial,
                    proposal=proposal,
                    receipt=accepted,
                )
            ),
        )
        assert proposal.identity == receipt.proposal.identity
        assert accepted.identity == receipt.identity
        assert fingerprint(accepted.checkpoint) == fingerprint(receipt.checkpoint)
        serial = accepted.checkpoint
    assert serial.identity == saved.checkpoint.identity
    if kind == "passive" and profile == "normal":
        replayed = batch.replay_world(saved)
        assert batch.world_record(replayed) == batch.world_record(saved)
    compare_reference(kind + "-" + law + "-" + profile, source, receipts)
    evidence(
        "protein-batch-loop-serial-" + kind + "-" + law + "-" + profile,
        dict(
            complete_loops=count,
            full_serial_proposals_receipts_and_states_exact=True,
            source_checkpoint=saved.base.identity,
            target_checkpoint=saved.checkpoint.identity,
            raw_history_manifests=str(output),
        ),
    )


@pytest.mark.parametrize("law", ("native", "stable"))
def test_guarded_worlds_still_evolve_complete_ionic_loops(law):
    sources = tuple(
        world(law=law, profile=profile, label=profile, index=111 + i, native_tape=i)
        for i, profile in enumerate(("INIT", "fast", "protein_off"))
    )
    result = batch.run_batch(sources, steps=2, budget=declared)
    assert len(result.rounds) == 2 and all(row.valid.all() for row in result.rounds)
    for source, target in zip(sources, result.worlds, strict=True):
        assert target.checkpoint.component.stream == source.checkpoint.component.stream
        assert target.checkpoint.component.loop_calls == source.checkpoint.component.loop_calls + 2
        assert target.checkpoint.step_index > source.checkpoint.step_index
        assert fingerprint(target.checkpoint.state) != fingerprint(source.checkpoint.state)
        assert len(target.history) == 2
        assert all(
            a.receipt.cumulative_accounting["valid"] for r in result.rounds for a in r.attempts
        )


@pytest.mark.parametrize("law", ("native", "stable"))
def test_batch_reorder_and_partition_keep_complete_worlds_and_actual_tapes(law, monkeypatch):
    sources = tuple(
        world(law=law, label="order" + str(i), index=131 + i, native_tape=i) for i in range(3)
    )
    proposed = batch.propose_batch(sources)
    budgets = {row.source.world_id: declared(row.source, row.proposal) for row in proposed.worlds}
    with monkeypatch.context() as m:
        m.setattr(streams, "draw", no_draw)
        forward = batch.accept_batch(sources, proposed, budgets)
        reverse = batch.accept_batch(sources[::-1], proposed, budgets)
        left = batch.accept_batch(
            sources[:1], proposed, {sources[0].world_id: budgets[sources[0].world_id]}
        )
        right = batch.accept_batch(
            sources[1:], proposed, {w.world_id: budgets[w.world_id] for w in sources[1:]}
        )
    assert forward.valid.tolist() == reverse.valid.tolist() == [True] * 3
    assert [batch.world_record(w) for w in forward.worlds] == [
        batch.world_record(w) for w in reverse.worlds[::-1]
    ]
    assert [batch.world_record(w) for w in forward.worlds] == [
        batch.world_record(w) for w in (*left.worlds, *right.worlds)
    ]


@pytest.mark.parametrize("law", ("native", "stable"))
def test_failed_worlds_keep_complete_parents_raw_trials_and_are_not_retried(tmp_path, law):
    sources = tuple(
        world(law=law, label=label, index=151 + i, native_tape=i, huge=label == "protein_failure")
        for i, label in enumerate(("good", "local_failure", "protein_failure", "global_failure"))
    )
    before = [fingerprint(w.checkpoint) for w in sources]

    def budgets(source, proposal):
        offset = (
            8 * 2e-8
            if source.world_id == "local_failure"
            else 0.6 * 2e-8
            if source.world_id == "global_failure"
            else 0.0
        )
        return budget(proposal, offset=offset)

    result = batch.run_batch(sources, steps=3, budget=budgets)
    raw_folder = (
        Path(os.environ["CELLS_COMPONENT_EVIDENCE"]) / "batch-failures" / law
        if os.environ.get("CELLS_COMPONENT_EVIDENCE")
        else tmp_path
    )
    for index, attempt in enumerate(a for r in result.rounds for a in r.attempts):
        persistence.write_raw_evidence(raw_folder / ("attempt-" + str(index)), attempt.payload)
    assert [r.valid.tolist() for r in result.rounds] == [
        [True, False, False, True],
        [True, False],
        [True],
    ]
    assert [w.checkpoint.loop_index for w in result.worlds] == [3, 0, 0, 1]
    assert result.worlds[1] is sources[1] and result.worlds[2] is sources[2]
    assert all(
        fingerprint(w.checkpoint) == original for w, original in zip(sources, before, strict=True)
    )
    attempts = tuple(a for r in result.rounds for a in r.attempts)
    failed = [a for a in attempts if not a.accepted]
    assert len(failed) == 3
    for attempt in failed:
        assert attempt.world is attempt.parent
        assert attempt.failure is not None
    physical = next(a for a in failed if a.parent.world_id == "protein_failure")
    failure = physical.failure
    assert failure.packet is not None and len(failure.intervals) > 0
    assert failure.stream.next_tick == physical.parent.checkpoint.component.stream.next_tick + 1
    trial = failure.failure.trial
    assert np.any(trial.protein.cell_mol_m3 < 0) or np.any(trial.protein.environment_mol_m3 < 0)
    source = failure.preparation.source_state
    inputs = dict(
        binding=batch.loop.held.units.binding_record(physical.parent.checkpoint.origin.binding),
        source=provider.source_record(source),
        threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
    )
    expected = packet_reference.provide(**inputs)
    actual_packet = perturb.draw_manifest(
        failure.packet, physical.parent.checkpoint.origin.binding.component
    )
    assert canonical(expected["packet"]) == canonical(actual_packet)
    assert canonical(expected["successor_stream"]) == canonical(
        streams.stream_record(failure.stream)
    )
    raw_path = persistence.write_raw_evidence(
        raw_folder / "actual-failed-component",
        batch.raw(
            dict(
                source=source,
                actual_packet=failure.packet,
                actual_successor=failure.stream,
                actual_component_trial=trial,
                actual_ionic_intervals=failure.intervals,
                full_failure=failure,
            )
        ),
    )
    saved_path = persistence.write_batch_checkpoint(
        raw_folder / "failed-cohort", result.worlds, attempts=attempts
    )
    saved = persistence.load_batch_checkpoint(saved_path)
    assert [batch.world_record(w) for w in saved.worlds] == [
        batch.world_record(w) for w in result.worlds
    ]
    assert len(saved.attempts) == len(attempts)
    for actual, restored in zip(
        sorted(attempts, key=lambda a: (a.parent.world_id, a.parent.checkpoint.loop_index)),
        sorted(saved.attempts, key=lambda a: (a.world_id, a.source.loop_index)),
        strict=True,
    ):
        assert batch.raw_record(actual.payload) == batch.raw_record(restored.payload)
    evidence(
        "protein-batch-loop-failed-provider-" + law,
        dict(
            inputs=inputs,
            expected=expected,
            actual_packet=actual_packet,
            actual_successor=streams.stream_record(failure.stream),
            actual_trial_archive=str(raw_path),
            actual_trial_manifest_sha256=persistence._sha(raw_path / "manifest.json"),
            full_attempts_archive=str(saved_path),
            full_attempts_manifest_sha256=persistence._sha(saved_path / "manifest.json"),
            failed_parent_checkpoint=physical.parent.checkpoint.identity,
            global_refusal_report=batch.loop.transition._record(
                next(a for a in failed if a.parent.world_id == "global_failure").failure.report
            ),
        ),
    )


@pytest.mark.parametrize(
    "edit",
    ("advanced_parent", "cross_world", "ionic_trial", "packet", "successor", "missing_budget"),
)
def test_stale_complete_loop_inputs_refuse_only_their_world(edit):
    sources = (world(label="stale-a", index=171), world(label="stale-b", index=172, native_tape=1))
    proposed = batch.propose_batch(sources)
    budgets = {r.source.world_id: declared(r.source, r.proposal) for r in proposed.worlds}
    rows = list(proposed.worlds)
    proposal = rows[0].proposal
    if edit == "advanced_parent":
        accepted = batch.accept_batch(sources, proposed, budgets)
        sources = (accepted.worlds[0], sources[1])
    elif edit == "cross_world":
        proposal = rows[1].proposal
    elif edit == "ionic_trial":
        interval = proposal.intervals[-1]
        state = interval.trial.proposed_state
        fields = list(state)
        fields[0] = fields[0] + 1e-6
        trial = interval.trial._replace(proposed_state=type(state)(*fields))
        proposal = replace(
            proposal, intervals=(*proposal.intervals[:-1], replace(interval, trial=trial))
        )
    elif edit == "packet":
        original = proposal.component_transition.packet
        changed = perturb.prescribed_draw(
            original.site,
            original.tick,
            original.values[::-1],
            sources[0].checkpoint.origin.binding.component,
            provenance=json.loads(original.provenance_json),
        )
        proposal = replace(
            proposal, component_transition=replace(proposal.component_transition, packet=changed)
        )
    elif edit == "successor":
        component = proposal.component_transition.state
        state = perturb.native_stream_manifest(component.stream.rng)["state"]
        state[4] += 0.125
        rng = perturb._native_stream(state, np.__version__)
        component = replace(component, stream=replace(component.stream, rng=rng))
        proposal = replace(
            proposal, component_transition=replace(proposal.component_transition, state=component)
        )
    else:
        budgets.pop(sources[0].world_id)
    if edit not in ("advanced_parent", "missing_budget"):
        proposal = replace(proposal, identity="")
        proposal = replace(proposal, identity=batch.loop.proposal_record(proposal)["identity"])
        row = replace(rows[0], proposal=proposal, identity="")
        rows[0] = replace(row, identity=batch.proposal_record(row)["identity"])
    result = batch.accept_batch(sources, batch.BatchLoopProposal(tuple(rows)), budgets)
    assert result.valid.tolist() == [False, True]
    assert result.worlds[0] is sources[0]
    assert result.attempts[0].payload["proposal"] is not None


@pytest.mark.parametrize("law,terminal", (("native", "calls"), ("stable", "tick")))
def test_terminal_component_counter_commits_once_then_preserves_the_whole_parent(law, terminal):
    sources = (
        world(law=law, label="terminal", index=191, terminal=terminal),
        world(law=law, label="neighbor", index=192),
    )
    result = batch.run_batch(sources, steps=2, budget=declared)
    assert [r.valid.tolist() for r in result.rounds] == [[True, True], [False, True]]
    assert result.worlds[0] is result.rounds[0].worlds[0]
    assert result.worlds[1].checkpoint.loop_index == 2
    if terminal == "calls":
        assert result.worlds[0].checkpoint.component.loop_calls == 2**64 - 1
    else:
        assert result.worlds[0].checkpoint.component.stream.next_tick == 2**64 - 1
        assert result.rounds[1].attempts[0].failure.packet is None


@pytest.mark.parametrize("profile", ("duplicate_name", "duplicate_owner", "mixed_engine"))
def test_ambiguous_cohort_refuses_before_ionic_evolution_or_draw(profile, monkeypatch):
    first = world(label="envelope", index=211)
    if profile == "duplicate_name":
        second = world(label="envelope", index=212)
    elif profile == "duplicate_owner":
        second = batch.initialise_world("other-label", first.spec, first.checkpoint)
    else:
        second = world(law="stable", label="other-engine", index=212)
    with monkeypatch.context() as m:
        m.setattr(streams, "draw", no_draw)
        with pytest.raises(batch.BatchLoopRejected) as error:
            batch.propose_batch((first, second))
    assert error.value.worlds[0] is first


def test_raw_failure_codec_keeps_nonfinite_payloads_signs_dtypes_and_zero_dimensions(tmp_path):
    words = np.asarray(
        [0x7FF8000000000042, 0xFFF8000000000011, 0x8000000000000000, 1, 0x7FF0000000000000],
        dtype=np.uint64,
    )
    value = batch.raw(
        dict(
            actual_trial=words.view(np.float64),
            actual_words=words,
            scalar=np.asarray(-0.0),
            control=np.asarray(False),
        )
    )
    path = persistence.write_raw_evidence(tmp_path / "raw", value)
    restored = persistence.load_raw_evidence(path)
    assert batch.raw_record(restored) == batch.raw_record(value)
    assert restored["scalar"].shape == () and restored["scalar"].dtype == np.float64
    assert not restored["actual_trial"].flags.writeable
    assert np.array_equal(restored["actual_trial"].view(np.uint64), words)


@pytest.mark.parametrize("edit", ("array_bits", "missing_file", "manifest"))
def test_raw_attempt_archive_refuses_changed_or_incomplete_evidence(tmp_path, edit):
    path = persistence.write_raw_evidence(
        tmp_path / "raw", batch.raw(dict(trial=np.array([1.0, -2.0])))
    )
    if edit == "array_bits":
        with np.load(path / "arrays.npz", allow_pickle=False) as data:
            values = {name: np.array(data[name]) for name in data.files}
        values["leaf000000"][0] += 0.125
        with (path / "arrays.npz").open("wb") as handle:
            np.savez(handle, **values)
    elif edit == "missing_file":
        (path / "arrays.npz").unlink()
    else:
        record = json.loads((path / "manifest.json").read_text())
        record["complete"] = False
        (path / "manifest.json").write_text(json.dumps(record))
    with pytest.raises((ConfigError, OSError)):
        persistence.load_raw_evidence(path)
