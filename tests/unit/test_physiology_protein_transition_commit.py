"""Atomic component commits from real packets and complete energy admission."""

import hashlib
import json
import os
import platform
import sys
from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import jaxlib
import numpy as np
import pytest

from cells.core import physiology_perturbation_phases as phases
from cells.core import physiology_protein_packet_provider as provider
from cells.core import physiology_protein_transition_commit as commit
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.numerics import physiology_protein_transition_commit_arrays as arrays
from cells.processes import betse_perturbations as perturb
from tests.unit.test_physiology_protein_drive_arrays import PROVENANCE
from tests.unit.test_physiology_protein_electrical_arrays import prepare
from tests.unit.test_physiology_protein_interval_accounting import evidence
from tests.unit.test_physiology_protein_packet_provider import (
    canonical,
    next_source,
    reduced_sources,
    source_case,
)
from tests.unit.test_physiology_protein_transition_arrays import host_law, plain
from tests.unit.test_physiology_protein_work_arrays import frame
from tests.unit.test_physiology_tissue_step import KINDS, control
from validation.tissue import physiology_protein_packet_provider_reference as packet_reference
from validation.tissue import physiology_protein_transition_commit_reference as reference


@pytest.fixture(scope="module", autouse=True)
def runtime_evidence():
    phase = os.environ.get("CELLS_PROTEIN_COMMIT_PHASE", "local")
    affinity = sorted(os.sched_getaffinity(0))
    if phase != "local":
        assert affinity == [7]
    evidence(
        "protein-transition-commit-runtime-" + phase,
        dict(
            pid=os.getpid(),
            measured_child_cpu_affinity=affinity,
            python_version=platform.python_version(),
            python_full_version=sys.version,
            python_implementation=sys.implementation.name,
            numpy_version=np.__version__,
            jax_version=jax.__version__,
            jaxlib_version=jaxlib.__version__,
            backend=jax.default_backend(),
            devices=[str(device) for device in jax.devices()],
            x64_enabled=bool(jax.config.x64_enabled),
            disable_jit=bool(jax.config.jax_disable_jit),
            threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
        ),
    )


def bits(value):
    return [(a.dtype.str, a.shape, a.tobytes()) for a in map(np.asarray, jax.tree.leaves(value))]


def world_source(source, world):
    rng = source.stream.rng
    if type(rng) is perturb.StableCoordinates:
        rng = perturb.StableCoordinates(rng.seed, world)
    # Native words/cache are copied from an explicitly supplied stream. The
    # world label never becomes a native seed, and identical owned tapes are legal.
    return replace(source, stream=replace(source.stream, rng=rng, world_id=world))


def request(spec, point, binding, parent, *, anchor=None, budget="balanced", supplied=None):
    supplied = provider.provide(parent, binding) if supplied is None else supplied
    anchor = parent if anchor is None else anchor
    trial = next_source(parent, supplied)
    held = replace(parent, diffusion=trial.diffusion)
    b, e, _, _, implementation = prepare(spec, point, binding, anchor, held, trial)
    parameters = frame(spec) | dict(implementation=implementation)
    work = arrays.transition.drive.endpoint_work.evaluate(
        anchor.protein,
        parent.protein,
        trial.protein,
        b,
        e,
        supplied.encoded.geometry.work_geometry,
        **parameters,
        xp=np,
    )
    external = float(work.conditional_reversible_work_pJ)
    dissipated = 0.0
    if budget == "missing_work":
        external += 8 * arrays.transition.drive._energy_limit(implementation)
    elif budget == "negative_dissipation":
        dissipated = -(2.0**-16)
        external += dissipated
    parameters.update(
        external_work_pJ=np.asarray(external),
        dissipated_free_energy_pJ=np.asarray(dissipated),
        budget_provenance=PROVENANCE,
    )
    return commit.CommitRequest(parent, binding, supplied, anchor.protein, b, e, parameters)


def source_equal(first, second, binding):
    assert canonical(provider.source_record(first)) == canonical(provider.source_record(second))
    assert bits((first.protein, first.diffusion)) == bits((second.protein, second.diffusion))
    assert bits(provider._stream(first.stream)) == bits(provider._stream(second.stream))
    commit.step.validate_state(first, binding.component)


def compare(name, spec, point, r, attempt):
    assert attempt.evaluation is not None, attempt.error
    declared = dict(
        raw=spec.to_dict(),
        state=point.state._asdict(),
        binding=units.binding_record(r.binding),
        held_control=control(spec, point.time)._asdict(),
        charge_reference=r.charge_reference._asdict(),
        source=plain(r.provided.encoded.source),
        packet=plain(r.provided.array_packet),
        **frame(spec),
        **{
            k: r.parameters[k]
            for k in ("external_work_pJ", "dissipated_free_energy_pJ", "budget_provenance")
        },
    )
    inputs = dict(
        binding=units.binding_record(r.binding),
        source=provider.source_record(r.parent),
        threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
        transition_inputs=declared,
    )
    inputs = json.loads(canonical(inputs))
    expected = reference.evaluate(**inputs)
    assert bool(expected["valid"]) == attempt.accepted
    numeric = attempt.evaluation.selection
    expected_stream = (
        expected["provider"]["successor_stream"] if attempt.accepted else inputs["source"]["stream"]
    )
    assert canonical(streams.stream_record(attempt.state.stream)) == canonical(expected_stream)
    actual_packet = (
        None
        if r.provided.packet is None
        else perturb.draw_manifest(r.provided.packet, r.binding.component)
    )
    assert canonical(actual_packet) == canonical(expected["provider"]["packet"])
    assert attempt.state.loop_calls == expected["state"]["loop_calls"]
    assert attempt.state.time_s == expected["state"]["time_s"]
    errors = {}
    for field in perturb.ProteinState._fields:
        value = np.asarray(getattr(numeric.state.protein, field))
        target = np.asarray(expected["state"]["protein"][field])
        budget = 3e-14 * abs(target) + 4 * abs(np.spacing(target))
        errors[field] = float(np.max(abs(value - target) / budget, initial=0))
    residual = attempt.evaluation.admission.declared_drive.energy_balance.balance_residual_pJ
    target = expected["admission"]["declared_drive"]["direct_SI_residual_pJ"]
    errors["SI_energy"] = abs(residual - target) / (3e-14 + 3e-10 * abs(target))
    # Compare the real uncommitted component with both frozen host phase finish
    # and the captured original transition law. Neither receives a fresh world seed.
    preparation = phases.prepare(r.parent, r.binding.component)
    host = phases.finish(r.parent, r.binding.component, preparation)
    proposed = next_source(r.parent, r.provided)
    source_equal(proposed, host.state, r.binding)
    host_law()(
        preparation,
        commit.step.PerturbationTransition(proposed, r.provided.packet, {}),
        r.binding.component,
    )
    if attempt.accepted:
        source_equal(attempt.state, host.state, r.binding)
    else:
        assert attempt.state is r.parent
        assert bits(numeric.state) == bits(r.provided.encoded.source)
    evidence(
        "protein-transition-commit-" + name,
        dict(
            inputs=inputs,
            expected=expected,
            actual=plain(attempt.evaluation),
            actual_host_state=provider.source_record(attempt.state),
            accepted=attempt.accepted,
            maximum_error_fraction=max(errors.values()),
            errors=errors,
            frozen_host_phase_and_transition_law=True,
            component_only=True,
        ),
    )
    assert max(errors.values()) <= 1


def no_draw(*args, **kwargs):
    raise AssertionError("Admission, decoding and publication must not sample")


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("law", ("native", "stable"))
@pytest.mark.parametrize("at_event", (False, True))
def test_full_family_real_packet_commit_matches_frozen_host_and_independent_SI(
    kind, law, at_event, monkeypatch
):
    spec, point, binding, parent = source_case(kind, law, at_event=at_event)
    r = request(spec, point, binding, parent)
    original = bits((point.state, point.layout, r.before_endpoint, r.after_endpoint))
    with monkeypatch.context() as m:
        m.setattr(streams, "draw", no_draw)
        result = commit.commit_batch((r,))
    assert result.valid.tolist() == [True], result.attempts[0].error
    assert not result.valid.flags.writeable
    assert bits((point.state, point.layout, r.before_endpoint, r.after_endpoint)) == original
    compare(kind + "-" + law + "-" + str(at_event), spec, point, r, result.attempts[0])
    limit = 2e-8 if kind in ("passive", "ionic") else 1e-9
    assert (
        result.attempts[
            0
        ].evaluation.admission.declared_drive.energy_balance.physical_energy_tolerance_pJ
        == limit
    )


@pytest.mark.parametrize("law", ("native", "stable"))
@pytest.mark.parametrize(
    "profile", ("INIT", "fast", "dynamic_off", "protein_off", "zero", "negative")
)
def test_guards_and_enabled_zero_commit_exact_original_component_semantics(law, profile):
    spec, point, binding, parent = source_case(law=law, profile=profile)
    r = request(spec, point, binding, parent)
    result = commit.commit_batch((r,))
    assert result.valid.tolist() == [True], result.attempts[0].error
    active = profile in ("zero", "negative")
    assert result.states[0].stream.next_tick == parent.stream.next_tick + int(active)
    assert result.states[0].loop_calls == parent.loop_calls + 1
    assert result.states[0].time_s == parent.time_s + parent.controls.dt_s
    assert (r.provided.packet is not None) == active
    compare("guard-" + law + "-" + profile, spec, point, r, result.attempts[0])


@pytest.mark.parametrize("law", ("native", "stable"))
def test_mixed_budget_refusals_keep_complete_parents_and_full_trials(law, monkeypatch):
    rows = []
    for i, (profile, budget) in enumerate(
        (
            ("normal", "balanced"),
            ("zero", "balanced"),
            ("normal", "missing_work"),
            ("normal", "negative_dissipation"),
            ("dynamic_off", "balanced"),
        )
    ):
        spec, point, binding, parent = source_case(law=law, profile=profile)
        parent = world_source(parent, 2**40 + 101 + i)
        rows.append((spec, point, request(spec, point, binding, parent, budget=budget)))
    parents = [provider.source_record(r.parent) for _, _, r in rows]
    with monkeypatch.context() as m:
        m.setattr(streams, "draw", no_draw)
        result = commit.commit_batch([r for _, _, r in rows])
    assert result.valid.tolist() == [True, True, False, False, True]
    for i, ((spec, point, r), attempt) in enumerate(zip(rows, result.attempts, strict=True)):
        assert canonical(provider.source_record(r.parent)) == canonical(parents[i])
        assert attempt.trial is not None and attempt.provided is r.provided
        if not attempt.accepted:
            assert attempt.state is r.parent
            assert int(attempt.trial.loop_calls) == r.parent.loop_calls + 1
            assert int(attempt.trial.stream.next_tick) == r.parent.stream.next_tick + 1
        compare("mixed-" + law + "-" + str(i), spec, point, r, attempt)


@pytest.mark.parametrize("law", ("native", "stable"))
def test_repeated_commits_and_complete_stream_restart_replay(law):
    spec, point, binding, initial = source_case(law=law)
    carried = restarted = initial
    for i in range(4):
        r = request(spec, point, binding, carried, anchor=initial)
        restored = request(spec, point, binding, restarted, anchor=initial)
        a = commit.commit_batch((r,))
        b = commit.commit_batch((restored,))
        assert a.valid.tolist() == b.valid.tolist() == [True]
        source_equal(a.states[0], b.states[0], binding)
        compare("repeat-" + law + "-" + str(i), spec, point, r, a.attempts[0])
        carried = a.states[0]
        restarted = replace(
            b.states[0],
            stream=streams.restore_stream(
                streams.stream_record(b.states[0].stream),
                binding.component,
            ),
        )
    assert carried.loop_calls == 4 and carried.stream.next_tick == initial.stream.next_tick + 4


@pytest.mark.parametrize("law", ("native", "stable"))
def test_batch_order_and_padding_keep_named_owner_publication(law):
    named = {}
    for padded in (True, False):
        spec, point, binding, parent = source_case(law=law, at_event=not padded)
        requests = [
            request(spec, point, binding, world_source(parent, world)) for world in (101, 203)
        ]
        forward = commit.commit_batch(requests)
        reverse = commit.commit_batch(requests[::-1])
        assert forward.valid.tolist() == reverse.valid.tolist() == [True, True]
        for i, r in enumerate(requests):
            source_equal(forward.states[i], reverse.states[1 - i], binding)
            compare(
                "order-" + law + "-" + str(padded) + "-" + str(i),
                spec,
                point,
                r,
                forward.attempts[i],
            )
            packet = dict(
                zip(binding.component.membrane_ids, r.provided.packet.values, strict=True)
            )
            if padded:
                named[i] = packet
            elif law == "stable":
                assert packet == named[i]
            else:
                assert sorted(packet.values()) == sorted(named[i].values())


STALE = (
    "provider_world",
    "parent",
    "binding",
    "packet",
    "proposal",
    "before_field",
    "after_charge",
    "held_P",
    "temperature",
    "model",
    "reference",
    "successor",
)


@pytest.mark.parametrize("law", ("native", "stable"))
@pytest.mark.parametrize("edit", STALE)
def test_stale_cross_world_and_complete_physical_inputs_refuse_only_their_world(law, edit):
    spec, point, binding, parent = source_case(law=law)
    r = request(spec, point, binding, world_source(parent, 101))
    neighbor = request(spec, point, binding, world_source(parent, 203))
    if edit == "provider_world":
        r = replace(r, provided=neighbor.provided)
    elif edit == "parent":
        r = replace(r, parent=replace(r.parent, time_s=r.parent.controls.dt_s))
    elif edit == "binding":
        r = replace(
            r, binding=replace(binding, membrane_thickness_m=binding.membrane_thickness_m * 2)
        )
    elif edit == "packet":
        packet = r.provided.array_packet._replace(values=r.provided.array_packet.values[::-1])
        r = replace(r, provided=replace(r.provided, array_packet=packet))
    elif edit == "proposal":
        trial = r.provided.array_proposal.trial._replace(loop_calls=np.asarray(2, np.uint64))
        r = replace(
            r,
            provided=replace(
                r.provided, array_proposal=r.provided.array_proposal._replace(trial=trial)
            ),
        )
    elif edit == "before_field":
        r = replace(
            r,
            before_endpoint=r.before_endpoint._replace(
                potential_V=r.before_endpoint.potential_V + 0.001
            ),
        )
    elif edit == "after_charge":
        q = np.array(r.after_endpoint.protein_charge_increment_C)
        q[0] += 1e-15
        r = replace(r, after_endpoint=r.after_endpoint._replace(protein_charge_increment_C=q))
    elif edit == "held_P":
        p = r.before_endpoint.runtime_layout._replace(
            membrane_permeability=r.before_endpoint.runtime_layout.membrane_permeability * 1.01
        )
        r = replace(
            r,
            before_endpoint=r.before_endpoint._replace(runtime_layout=p),
            after_endpoint=r.after_endpoint._replace(runtime_layout=p),
        )
    elif edit == "temperature":
        r = replace(
            r, parameters=dict(r.parameters) | dict(temperature_K=r.parameters["temperature_K"] + 1)
        )
    elif edit == "model":
        r = replace(r, parameters=dict(r.parameters) | dict(implementation=commit.view.calcium))
    elif edit == "reference":
        r = replace(
            r,
            charge_reference=r.charge_reference._replace(
                cell_mol_m3=r.charge_reference.cell_mol_m3 * 1.001
            ),
        )
    else:
        successor = replace(
            r.provided.successor_stream, next_tick=r.provided.successor_stream.next_tick + 1
        )
        r = replace(r, provided=replace(r.provided, successor_stream=successor))
    result = commit.commit_batch((r, neighbor))
    assert result.valid.tolist() == [False, True], (edit, result.attempts[0].error)
    assert result.states[0] is r.parent
    assert result.attempts[0].provided is r.provided and result.attempts[0].trial is not None


@pytest.mark.parametrize("law", ("native", "stable"))
@pytest.mark.parametrize(
    "edit", ("valid", "float32", "int64", "shape", "protein", "trial", "check", "world")
)
def test_strict_decoder_rejects_stale_bits_shapes_dtypes_and_flags(law, edit, monkeypatch):
    spec, point, binding, parent = source_case(law=law)
    r = request(spec, point, binding, world_source(parent, 101))
    neighbor = request(spec, point, binding, world_source(parent, 203))
    expected = commit.commit_batch((r, neighbor))
    first, last = [a.evaluation.selection for a in expected.attempts]
    if edit == "valid":
        first = first._replace(valid=np.asarray(False))
    elif edit == "float32":
        first = first._replace(
            state=first.state._replace(time_s=first.state.time_s.astype(np.float32))
        )
    elif edit == "int64":
        first = first._replace(
            state=first.state._replace(loop_calls=first.state.loop_calls.astype(np.int64))
        )
    elif edit == "shape":
        first = first._replace(state=first.state._replace(time_s=first.state.time_s.reshape(1)))
    elif edit == "protein":
        protein = first.state.protein._replace(cell_mol_m3=first.state.protein.cell_mol_m3 * 1.001)
        first = first._replace(state=first.state._replace(protein=protein))
    elif edit == "trial":
        first = first._replace(trial=first.trial._replace(time_s=first.trial.time_s + 1))
    elif edit == "check":
        first = first._replace(checks=first.checks | dict(source_association=np.asarray(False)))
    else:
        first = last
    with monkeypatch.context() as m:
        m.setattr(streams, "draw", no_draw)
        result = commit.commit_batch((r, neighbor), selections=(first, last))
    assert result.valid.tolist() == [False, True]
    assert result.states[0] is r.parent
    assert result.attempts[0].diagnostics["stage"] == "strict_host_decoder"


@pytest.mark.parametrize("edit", ("cache_zero", "cache_sign", "word", "position"))
def test_strict_decoder_preserves_every_native_cache_and_word_bit(edit):
    spec, point, binding, parent = source_case()
    r = request(spec, point, binding, parent)
    good = commit.commit_batch((r,))
    selection = good.attempts[0].evaluation.selection
    rng = selection.state.stream.rng
    if edit == "cache_zero":
        rng = rng._replace(cached_gaussian=np.asarray(0.0))
    elif edit == "cache_sign":
        rng = rng._replace(cached_gaussian=-rng.cached_gaussian)
    elif edit == "word":
        words = np.array(rng.words)
        words[0] ^= np.uint32(1)
        rng = rng._replace(words=words)
    else:
        rng = rng._replace(position=rng.position + np.uint32(1))
    bad = selection._replace(
        state=selection.state._replace(stream=selection.state.stream._replace(rng=rng))
    )
    result = commit.commit_batch((r,), selections=(bad,))
    assert not result.valid[0] and result.states[0] is parent
    assert perturb.native_stream_manifest(good.states[0].stream.rng)["state"][4] == 1e-310


@pytest.mark.parametrize("law", ("native", "stable"))
@pytest.mark.parametrize(
    "profile", ("time", "loop", "active_tick", "inactive_tick", "final_call", "final_tick")
)
def test_clock_overflow_and_terminal_legal_commit_preserve_owned_state(law, profile):
    spec, point, binding, parent = source_case(
        law=law, profile="fast" if profile == "inactive_tick" else "normal"
    )
    base = request(spec, point, binding, parent)
    if profile == "time":
        parent = replace(parent, time_s=2.0**80)
    elif profile in ("loop", "final_call"):
        parent = replace(parent, loop_calls=2**64 - (1 if profile == "loop" else 2))
    else:
        parent = replace(
            parent,
            stream=replace(parent.stream, next_tick=2**64 - (2 if profile == "final_tick" else 1)),
        )
    try:
        supplied = provider.provide(parent, binding)
    except provider.PacketProviderRejected as failure:
        supplied = failure
    if isinstance(supplied, provider.PacketProviderRejected):
        r = replace(base, parent=parent, provided=supplied)
    else:
        r = request(spec, point, binding, parent, supplied=supplied)
    result = commit.commit_batch((r,))
    valid = profile in ("inactive_tick", "final_call", "final_tick")
    assert result.valid.tolist() == [valid], result.attempts[0].error
    if not valid:
        assert result.states[0] is parent and supplied.packet is None
    elif profile == "final_call":
        assert result.states[0].loop_calls == 2**64 - 1
    elif profile == "final_tick":
        assert result.states[0].stream.next_tick == 2**64 - 1


@pytest.mark.parametrize("law", ("native", "stable"))
def test_failed_real_provider_retains_packet_successor_and_full_trial_parent(law):
    spec, point, binding, parent = source_case(law=law)
    base = request(spec, point, binding, parent)
    parent = replace(parent, controls=replace(parent.controls, dynamic_level_mol_m2_s=1e8))
    before = provider.source_record(parent)
    with pytest.raises(provider.PacketProviderRejected) as error:
        provider.provide(parent, binding)
    failure = error.value
    r = replace(base, parent=parent, provided=failure)
    result = commit.commit_batch((r,))
    assert result.valid.tolist() == [False] and result.states[0] is parent
    attempt = result.attempts[0]
    assert attempt.trial is failure.array_proposal.trial and failure.packet is not None
    assert failure.successor_stream.next_tick == parent.stream.next_tick + 1
    assert canonical(provider.source_record(parent)) == canonical(before)
    inputs = dict(
        binding=units.binding_record(binding),
        source=before,
        threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
    )
    target = packet_reference.provide(**inputs)
    assert canonical(target["packet"]) == canonical(
        perturb.draw_manifest(failure.packet, binding.component)
    )
    assert canonical(target["successor_stream"]) == canonical(
        streams.stream_record(failure.successor_stream)
    )
    evidence(
        "protein-transition-commit-failed-provider-" + law,
        dict(
            inputs=inputs,
            expected=target,
            actual_packet=perturb.draw_manifest(failure.packet, binding.component),
            actual_successor=streams.stream_record(failure.successor_stream),
            full_trial_retained=True,
            exact_parent_retained=True,
        ),
    )


@pytest.mark.parametrize("profile", ("mixed_engines", "duplicate_owner", "selection_count"))
def test_batch_envelope_refuses_without_publishing_or_sampling(profile, monkeypatch):
    spec, point, binding, parent = source_case()
    first = request(spec, point, binding, parent)
    if profile == "mixed_engines":
        spec, point, binding, parent = source_case(law="stable")
        second = request(spec, point, binding, world_source(parent, 203))
    else:
        second = first
    with monkeypatch.context() as m:
        m.setattr(streams, "draw", no_draw)
        with pytest.raises(commit.CommitBatchRejected) as error:
            if profile == "selection_count":
                commit.commit_batch((first,), selections=())
            else:
                commit.commit_batch((first, second))
    assert error.value.parents[0] is first.parent


def reduced_requests():
    spec, point, binding, sources, _, _ = reduced_sources()
    profiles = (
        sources[0],
        sources[1],
        replace(sources[0], controls=replace(sources[0].controls, solver="fast")),
        sources[0],
    )
    parents = [world_source(parent, 2**40 + 101 + i) for i, parent in enumerate(profiles)]
    requests = [
        request(spec, point, binding, parent, budget="missing_work" if i == 3 else "balanced")
        for i, parent in enumerate(parents)
    ]
    batch = jax.tree.map(lambda *a: np.stack(a), *[r.provided.encoded.source for r in requests])
    return requests, batch, requests[0].provided.encoded.geometry


def boundary_path():
    folder = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if not folder:
        pytest.skip("Bounded qualification supplies actual retained compiled packets")
    return Path(folder) / "tissue-step/protein-transition-commit-real-provider.npz"


def provider_template(requests):
    records = [
        provider.StableProvidedPacket(
            np.asarray(True),
            np.asarray(True),
            r.provided.array_packet.present,
            r.provided.array_packet,
            r.provided.array_proposal,
            dict(source_preflight=np.asarray(True), associated_sampled_proposal=np.asarray(True)),
        )
        for r in requests
    ]
    return jax.tree.map(lambda *a: np.stack(a), *records)


def compare_compiled_provider(actual, expected):
    actual = jax.tree.map(np.asarray, actual)
    for name in ("valid", "preflight_valid", "packet_generated", "packet", "checks"):
        assert bits(getattr(actual, name)) == bits(getattr(expected, name))
    a, b = actual.proposal, expected.proposal
    for name in (
        "valid",
        "source_state",
        "source_packet",
        "source_geometry",
        "trial",
        "active",
        "packet_applied",
        "flux_mol_m2_s",
        "checks",
    ):
        assert bits(getattr(a, name)) == bits(getattr(b, name)), name
    gross = np.sum(abs(b.requested_cell_amount_change_mol), axis=-1) + np.sum(
        abs(b.requested_environment_amount_change_mol), axis=-1
    )
    maximum = 0.0
    for name in (
        "requested_cell_amount_change_mol",
        "requested_environment_amount_change_mol",
        "represented_cell_amount_change_mol",
        "represented_environment_amount_change_mol",
        "requested_balance_residual_mol",
    ):
        value, target = getattr(a, name), getattr(b, name)
        scale = gross.reshape(gross.shape + (1,) * (target.ndim - gross.ndim))
        budget = 3e-13 * scale + 4 * abs(np.spacing(target))
        difference = abs(value - target)
        assert np.all((budget > 0) | (difference == 0))
        ratio = np.divide(difference, budget, out=np.zeros_like(difference), where=budget > 0)
        maximum = max(maximum, float(np.max(ratio, initial=0)))
    assert maximum <= 1
    return maximum


def test_cpu_jax_real_owned_provider_boundary_for_atomic_commit():
    requests, batch, geometry = reduced_requests()
    g = jax.tree.map(jnp.asarray, geometry)
    compiled = jax.jit(jax.vmap(lambda source: provider.stable_packet_arrays(source, g)))
    actual = compiled(jax.tree.map(jnp.asarray, batch))
    actual.valid.block_until_ready()
    leaves = jax.tree.leaves(jax.tree.map(np.asarray, (batch, geometry, actual)))
    path = boundary_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **{f"leaf{i:04d}": a for i, a in enumerate(leaves)})
    path.with_suffix(".json").write_text(
        json.dumps(
            dict(
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                leaf_count=len(leaves),
                provider_source_sha256=hashlib.sha256(
                    Path(provider.__file__).read_bytes()
                ).hexdigest(),
                shapes=[list(a.shape) for a in leaves],
                dtypes=[a.dtype.str for a in leaves],
                actual_real_provider=True,
                distinct_world_owners=True,
                threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
            ),
            indent=2,
        )
        + "\n"
    )
    np.testing.assert_array_equal(actual.valid, [True] * 4)
    diagnostic_error = compare_compiled_provider(actual, provider_template(requests))
    evidence(
        "protein-transition-commit-cpu-provider-comparison",
        dict(
            exact_packets_complete_states_and_cache_bits=True,
            maximum_requested_diagnostic_error_fraction=diagnostic_error,
            diagnostic_budget="Frozen 3e-13 gross amount +4ULP; no changed material admission",
        ),
    )


def test_cpu_jax_staged_atomic_commit_and_strict_host_decoder():
    requests, batch, geometry = reduced_requests()
    path = boundary_path()
    metadata = json.loads(path.with_suffix(".json").read_text())
    assert metadata["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert (
        metadata["provider_source_sha256"]
        == hashlib.sha256(Path(provider.__file__).read_bytes()).hexdigest()
    )
    with np.load(path, allow_pickle=False) as archive:
        leaves = [np.array(archive[f"leaf{i:04d}"]) for i in range(metadata["leaf_count"])]
    assert [list(a.shape) for a in leaves] == metadata["shapes"]
    assert [a.dtype.str for a in leaves] == metadata["dtypes"]
    template = (batch, geometry, provider_template(requests))
    source, g, provided = jax.tree.structure(template).unflatten(leaves)
    assert bits((source, g)) == bits((batch, geometry))
    compare_compiled_provider(provided, template[2])
    shared = jax.tree.map(
        jnp.asarray,
        (
            requests[0].before_endpoint.source_state,
            requests[0].before_endpoint.source_control,
            requests[0].before_endpoint.runtime_layout,
        ),
    )
    fields = jax.tree.map(
        lambda *a: jnp.stack(a), *[(r.before_endpoint[3:], r.after_endpoint[3:]) for r in requests]
    )
    reference_batch = jax.tree.map(lambda *a: jnp.stack(a), *[r.charge_reference for r in requests])
    fixed = {k: v for k, v in requests[0].parameters.items() if k != "external_work_pJ"}
    geometry_jax = jax.tree.map(jnp.asarray, g)

    def finish(s, packet, proposal, reference_protein, before, after, external):
        endpoint = arrays.transition.drive.endpoint_work.endpoints.ArrayEndpoint
        answer = arrays._finish(
            s,
            packet,
            geometry_jax,
            proposal,
            reference_protein,
            endpoint(*shared, *before),
            endpoint(*shared, *after),
            **fixed,
            external_work_pJ=external,
            xp=jnp,
        )
        return answer.selection

    compiled = jax.jit(jax.vmap(finish))
    args = jax.tree.map(jnp.asarray, (source, provided.packet, provided.proposal))
    external = jnp.asarray([r.parameters["external_work_pJ"] for r in requests])
    selection = compiled(*args, reference_batch, *fields, external)
    selection.valid.block_until_ready()
    np.testing.assert_array_equal(selection.valid, [True, True, True, False])

    def rows(value):
        return [jax.tree.map(lambda a, world=i: np.asarray(a[world]), value) for i in range(4)]

    with pytest.MonkeyPatch.context() as m:
        m.setattr(streams, "draw", no_draw)
        decoded = commit.commit_batch(requests, selections=rows(selection))
    assert decoded.valid.tolist() == [True, True, True, False], [a.error for a in decoded.attempts]
    assert decoded.states[3] is requests[3].parent
    assert bits(rows(selection)[3].state) == bits(requests[3].provided.encoded.source)
    bad_packet = args[1]._replace(values=args[1].values.at[0, 0].set(0.25))
    stale = compiled(args[0], bad_packet, args[2], reference_batch, *fields, external)
    stale.valid.block_until_ready()
    np.testing.assert_array_equal(stale.valid, [False, True, True, False])
    refused = commit.commit_batch(requests, selections=rows(stale))
    assert refused.valid.tolist() == [False, True, True, False]
    assert refused.states[0] is requests[0].parent and refused.states[3] is requests[3].parent
    assert bits(rows(stale)[0].state) == bits(requests[0].provided.encoded.source)
    overflow = args[0]._replace(loop_calls=args[0].loop_calls.at[0].set(jnp.uint64(2**64 - 1)))
    overflow_result = compiled(overflow, args[1], args[2], reference_batch, *fields, external)
    overflow_result.valid.block_until_ready()
    np.testing.assert_array_equal(overflow_result.valid, [False, True, True, False])
    assert bits(rows(overflow_result)[0].state) == bits(
        jax.tree.map(lambda a: np.asarray(a[0]), overflow)
    )
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    evidence(
        "protein-transition-commit-cpu-staged",
        dict(
            valid=np.asarray(selection.valid),
            stale_valid=np.asarray(stale.valid),
            overflow_valid=np.asarray(overflow_result.valid),
            decoded_valid=decoded.valid,
            exact_parent_bits_preserved=True,
            strict_host_decoding=True,
            actual_provider_boundary_sha256=metadata["sha256"],
            compiled_scope=(
                "Actual stable provider and separate complete passive admission/atomic selection; "
                "no charged-loop or fused/native sampling credit"
            ),
        ),
    )
