"""Real owned packets, independent engine replay and transition association."""

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_protein_packet_provider as provider
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.processes import betse_perturbations as perturb
from tests.unit.test_physiology_protein_drive_arrays import (
    PROVENANCE,
    host_residual,
    minimal_source,
    ulp_error,
)
from tests.unit.test_physiology_protein_electrical_arrays import prepare
from tests.unit.test_physiology_protein_interval_accounting import evidence
from tests.unit.test_physiology_protein_transition_arrays import plain
from tests.unit.test_physiology_protein_work_arrays import frame
from tests.unit.test_physiology_tissue_binding import arguments, component_state, definition
from tests.unit.test_physiology_tissue_step import KINDS, case, control
from validation.tissue import physiology_protein_packet_provider_reference as reference
from validation.tissue import physiology_protein_transition_arrays_reference as transition_reference


def source_case(kind="passive", law="native", profile="normal", *, at_event=False):
    spec, point, binding, base, _ = case(kind, at_event=at_event, source_dt_scale=0.5)
    return spec, point, binding, make_source(spec, binding, base, law, profile)


def make_source(spec, binding, base, law, profile="normal"):
    k = binding.component.kernel
    scale = max(
        np.max(np.sum(abs(k.cell_surface_map), axis=1) / k.cell_volume_m3),
        np.max(np.sum(abs(k.environment_surface_map), axis=1) / k.environment_effective_volume_m3),
    )
    flags = dict(phase="SIM", solver="normal", dynamic_enabled=True, protein_enabled=True)
    flags.update(
        dict(
            INIT=dict(phase="INIT"),
            fast=dict(solver="fast"),
            dynamic_off=dict(dynamic_enabled=False),
            protein_off=dict(protein_enabled=False),
        ).get(profile, {})
    )
    level = (
        0.0
        if profile == "zero"
        else (2e-5 / (spec.execution.dt * scale)) * (-1 if profile == "negative" else 1)
    )
    controls = perturb.Controls(
        **flags, static_level=2.0, dynamic_level_mol_m2_s=level, dt_s=spec.execution.dt
    )
    if law == "native":
        state = perturb.native_stream_manifest(base.stream.rng)["state"]
        state[3], state[4] = 1, 1e-310
        rng = perturb._native_stream(state, np.__version__)
    else:
        rng = perturb.StableCoordinates(17, 2**40 + 7)
    stream = streams.new_stream(
        binding.component,
        rng,
        stream_id="real-owned-protein",
        world_id=2**40 + 7,
        next_tick=2**40 + 31,
    )
    protein = perturb.ProteinState(
        np.full(k.cell_volume_m3.shape, 2.0**-10),
        np.full(k.owner.shape, 1e99),
        np.full(k.environment_effective_volume_m3.shape, 3 * 2.0**-10),
    )
    return replace(
        base,
        protein=protein,
        stream=stream,
        controls=controls,
        time_s=0.0,
        loop_calls=0,
        diffusion=base.diffusion._replace(scheduled_m2_s=-0.125 * base.diffusion.base_m2_s),
    )


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=lambda a: np.asarray(a).tolist(),
    )


def compare(name, source, binding):
    original = provider.source_record(source)
    actual = provider.provide(source, binding)
    inputs = dict(
        binding=units.binding_record(binding),
        source=original,
        threefry_partitionable=actual.diagnostics["jax_threefry_partitionable"],
    )
    expected = reference.provide(**inputs)
    packet = (
        None if actual.packet is None else perturb.draw_manifest(actual.packet, binding.component)
    )
    assert canonical(packet) == canonical(expected["packet"])
    assert canonical(streams.stream_record(actual.successor_stream)) == canonical(
        expected["successor_stream"]
    )
    assert canonical(plain(actual.encoded.source)) == canonical(expected["array_source"])
    assert canonical(plain(actual.array_packet)) == canonical(expected["array_packet"])
    errors = {}
    for field in perturb.ProteinState._fields:
        value = np.asarray(getattr(actual.array_proposal.trial.protein, field))
        target = np.asarray(expected["proposal"]["trial"]["protein"][field])
        budget = 3e-14 * abs(target) + 4 * abs(np.spacing(target))
        errors[field] = float(np.max(abs(value - target) / budget, initial=0))
    evidence(
        "protein-packet-provider-" + name,
        dict(
            inputs=inputs,
            expected=expected,
            actual_packet=packet,
            actual_successor=streams.stream_record(actual.successor_stream),
            actual_proposal=plain(actual.array_proposal),
            maximum_error_fraction=max(errors.values()),
            errors=errors,
            native_and_stable_laws_distinct=True,
            loop_commit=False,
        ),
    )
    assert max(errors.values()) <= 1
    assert canonical(provider.source_record(source)) == canonical(original)
    assert actual.array_proposal.valid
    for value in jax.tree.leaves(
        (actual.encoded.source, actual.array_packet, actual.array_proposal)
    ):
        assert not value.flags.writeable
    return actual


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("law", ("native", "stable"))
@pytest.mark.parametrize("at_event", (False, True))
def test_real_packets_and_complete_successors_match_independent_engines(kind, law, at_event):
    _, _, binding, source = source_case(kind, law, at_event=at_event)
    compare(kind + "-" + law + "-" + str(at_event), source, binding)


@pytest.mark.parametrize("law", ("native", "stable"))
@pytest.mark.parametrize(
    "profile", ("INIT", "fast", "dynamic_off", "protein_off", "zero", "negative")
)
def test_original_guards_and_enabled_zero_sampling(law, profile, monkeypatch):
    _, _, binding, source = source_case(law=law, profile=profile)
    calls = []
    sampler = perturb.sample_native if law == "native" else perturb.sample_stable

    def counted(*a, **kw):
        calls.append(kw["site"])
        return sampler(*a, **kw)

    monkeypatch.setattr(perturb, "sample_native" if law == "native" else "sample_stable", counted)
    actual = compare("guard-" + law + "-" + profile, source, binding)
    active = profile in ("zero", "negative")
    assert calls == (["protein_flux"] if active else [])
    assert actual.successor_stream.next_tick == source.stream.next_tick + int(active)
    if profile == "zero":
        assert actual.packet is not None and np.all(actual.array_proposal.flux_mol_m2_s == 0)
        assert np.all(
            actual.array_proposal.trial.protein.membrane_mol_m3 != source.protein.membrane_mol_m3
        )
    if not active:
        assert actual.successor_stream is source.stream


def next_source(parent, supplied):
    trial = supplied.array_proposal.trial
    return replace(
        parent,
        protein=trial.protein,
        diffusion=trial.diffusion,
        stream=supplied.successor_stream,
        time_s=float(trial.time_s),
        loop_calls=int(trial.loop_calls),
    )


@pytest.mark.parametrize("law", ("native", "stable"))
def test_owned_stream_restart_replays_successive_actual_packets(law):
    _, _, binding, source = source_case(law=law)
    first = compare("restart-" + law + "-0", source, binding)
    carried = next_source(source, first)
    restarted = replace(
        carried,
        stream=streams.restore_stream(streams.stream_record(carried.stream), binding.component),
    )
    for index in range(1, 4):
        a = compare("restart-" + law + "-" + str(index), carried, binding)
        b = provider.provide(restarted, binding)
        assert perturb.draw_manifest(a.packet, binding.component) == perturb.draw_manifest(
            b.packet, binding.component
        )
        assert streams.stream_record(a.successor_stream) == streams.stream_record(
            b.successor_stream
        )
        carried, restarted = next_source(carried, a), next_source(restarted, b)


@pytest.mark.parametrize("law", ("native", "stable"))
def test_owner_order_and_padding_preserve_each_original_engine_semantics(law):
    original = None
    for padded, reverse in ((True, False), (False, True)):
        from cells.core.specs import parse_spec

        spec = parse_spec(definition("passive", padded=padded))
        binding = units.bind_tissue(spec, **arguments(spec, reverse=reverse))
        source = make_source(spec, binding, component_state(binding), law)
        actual = compare("order-" + law + "-" + str(reverse), source, binding)
        vector = np.asarray(actual.packet.values)
        named = dict(zip(binding.component.membrane_ids, vector, strict=True))
        if original is None:
            original = (vector, named)
        elif law == "stable":
            assert named == original[1]
        else:
            np.testing.assert_array_equal(vector, original[0])


@pytest.mark.parametrize("law", ("native", "stable"))
def test_world_labels_do_not_reseed_native_and_high_bits_remain_stable_keys(law):
    _, _, binding, source = source_case(law=law)
    changed_rng = (
        source.stream.rng
        if law == "native"
        else perturb.StableCoordinates(source.stream.rng.seed, 7)
    )
    changed = replace(
        source,
        stream=streams.new_stream(
            binding.component,
            changed_rng,
            stream_id=source.stream.stream_id,
            world_id=7,
            next_tick=source.stream.next_tick,
        ),
    )
    a = compare("world-" + law + "-high", source, binding)
    b = compare("world-" + law + "-low", changed, binding)
    if law == "native":
        np.testing.assert_array_equal(a.packet.values, b.packet.values)
        assert a.successor_stream.rng == b.successor_stream.rng
    else:
        assert not np.array_equal(a.packet.values, b.packet.values)


@pytest.mark.parametrize("law", ("native", "stable"))
def test_failed_sampled_proposal_retains_packet_successor_and_parent(law):
    _, _, binding, source = source_case(law=law)
    source = replace(source, controls=replace(source.controls, dynamic_level_mol_m2_s=1e8))
    before = provider.source_record(source)
    failures = []
    for _ in range(2):
        with pytest.raises(provider.PacketProviderRejected) as error:
            provider.provide(source, binding)
        failed = error.value
        failures.append(failed)
        assert failed.stage == "deterministic_proposal" and failed.packet is not None
        assert (
            failed.parent is source
            and failed.successor_stream.next_tick == source.stream.next_tick + 1
        )
        assert failed.array_packet is not None and not failed.array_proposal.valid
    assert perturb.draw_manifest(failures[0].packet, binding.component) == perturb.draw_manifest(
        failures[1].packet, binding.component
    )
    assert canonical(provider.source_record(source)) == canonical(before)
    expected = reference.provide(
        units.binding_record(binding),
        before,
        threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
    )
    evidence(
        "protein-packet-provider-failed-" + law,
        dict(
            inputs=dict(
                binding=units.binding_record(binding),
                source=before,
                threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
            ),
            expected=expected,
            actual_packet=perturb.draw_manifest(failures[0].packet, binding.component),
            actual_successor=streams.stream_record(failures[0].successor_stream),
            actual_proposal=plain(failures[0].array_proposal),
            expected_rejected=True,
            maximum_error_fraction=0.0,
        ),
    )


@pytest.mark.parametrize("profile", ("time", "loop", "active_tick", "inactive_tick"))
def test_clock_tick_preflight_refuses_before_sampling_or_allows_inactive_max(profile, monkeypatch):
    _, _, binding, source = source_case(profile="fast" if profile == "inactive_tick" else "normal")
    if profile == "time":
        source = replace(source, time_s=2.0**80)
    elif profile == "loop":
        source = replace(source, loop_calls=2**64 - 1)
    else:
        source = replace(source, stream=replace(source.stream, next_tick=2**64 - 1))

    def forbidden(*a, **kw):
        raise AssertionError("Invalid/off source must not sample")

    monkeypatch.setattr(perturb, "sample_native", forbidden)
    if profile == "inactive_tick":
        assert provider.provide(source, binding).packet is None
    else:
        with pytest.raises(provider.PacketProviderRejected) as error:
            provider.provide(source, binding)
        assert error.value.packet is None and error.value.successor_stream is source.stream


@pytest.mark.parametrize("partitionable", (True, False))
def test_stable_configured_bit_layout_matches_independent_threefry(partitionable):
    from jax._src import config

    _, _, binding, source = source_case(law="stable")
    with config.threefry_partitionable(partitionable):
        compare("config-" + str(partitionable), source, binding)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("law", ("native", "stable"))
def test_real_packet_proposal_and_declared_drive_share_actual_inputs(kind, law):
    spec, point, binding, source = source_case(kind, law)
    result = compare("drive-" + kind + "-" + law, source, binding)
    before = replace(source, diffusion=result.array_proposal.trial.diffusion)
    after = next_source(source, result)
    b, e, _, _, implementation = prepare(spec, point, binding, before, before, after)
    params = frame(spec) | dict(implementation=implementation)
    conditional = provider.transition.drive.endpoint_work.evaluate(
        source.protein,
        source.protein,
        after.protein,
        b,
        e,
        result.encoded.geometry.work_geometry,
        **params,
        xp=np,
    )
    external = float(conditional.conditional_reversible_work_pJ)
    budgets = dict(
        external_work_pJ=external, dissipated_free_energy_pJ=0.0, budget_provenance=PROVENANCE
    )
    actual = provider.transition.evaluate(
        result.encoded.source,
        result.array_packet,
        result.encoded.geometry,
        source.protein,
        b,
        e,
        **result.encoded.configuration,
        **params,
        **budgets,
        xp=np,
    )
    assert actual.valid
    declared = dict(
        raw=spec.to_dict(),
        state=point.state._asdict(),
        binding=units.binding_record(binding),
        held_control=control(spec, point.time)._asdict(),
        charge_reference=source.protein._asdict(),
        source=plain(result.encoded.source),
        packet=plain(result.array_packet),
        **frame(spec),
        **budgets,
    )
    expected = transition_reference.evaluate(**declared)
    value = actual.declared_drive.energy_balance.balance_residual_pJ
    wanted = expected["declared_drive"]["direct_SI_residual_pJ"]
    fraction = abs(value - wanted) / (3e-14 + 3e-10 * abs(wanted))
    evidence(
        "protein-packet-drive-" + kind + "-" + law,
        dict(
            inputs=declared,
            actual=plain(actual),
            expected=expected,
            maximum_error_fraction=fraction,
        ),
    )
    stale = result.array_packet._replace(values=result.array_packet.values[::-1])
    refused = provider.transition._finish(
        result.encoded.source,
        stale,
        result.encoded.geometry,
        result.array_proposal,
        source.protein,
        b,
        e,
        **params,
        **budgets,
        xp=np,
    )
    assert not refused.valid and not refused.checks["component_source_association"]
    assert fraction <= 1


def test_encode_does_not_sample_and_returns_owned_immutable_buffers(monkeypatch):
    _, _, binding, source = source_case()

    def forbidden(*a, **kw):
        raise AssertionError("Encoding is read only")

    monkeypatch.setattr(streams, "draw", forbidden)
    before = provider.source_record(source)
    encoded = provider.encode_source(source, binding)
    for value in jax.tree.leaves((encoded.source, encoded.geometry)):
        assert not value.flags.writeable
    assert canonical(provider.source_record(source)) == canonical(before)


def test_cpu_jax_real_stable_provider_mixed_guards_and_invalid_worlds():
    profiles = ("normal", "INIT", "fast", "dynamic_off", "protein_off", "zero", "negative")
    fixtures = [source_case(law="stable", profile=p) for p in profiles]
    expected = [provider.provide(s, b) for _, _, b, s in fixtures]
    encoded = [e.encoded for e in expected]
    batch = jax.tree.map(lambda *a: jnp.stack(a), *[e.source for e in encoded])
    geometry = jax.tree.map(jnp.asarray, encoded[0].geometry)
    compiled = jax.jit(jax.vmap(lambda s: provider.stable_packet_arrays(s, geometry)))
    actual = compiled(batch)
    actual.valid.block_until_ready()
    np.testing.assert_array_equal(actual.valid, [True] * len(profiles))
    for i, e in enumerate(expected):
        np.testing.assert_array_equal(actual.packet.values[i], e.array_packet.values)
        assert bool(actual.packet_generated[i]) == (e.packet is not None)
        for a, b in zip(
            jax.tree.leaves(jax.tree.map(lambda v, world=i: np.asarray(v[world]), actual.packet)),
            jax.tree.leaves(e.array_packet),
            strict=True,
        ):
            np.testing.assert_array_equal(a, b)
    bad = batch._replace(
        stream=batch.stream._replace(
            next_tick=batch.stream.next_tick.at[0].set(jnp.uint64(2**64 - 1))
        )
    )
    refused = compiled(bad)
    refused.valid.block_until_ready()
    assert not bool(refused.valid[0]) and not bool(refused.packet_generated[0])
    np.testing.assert_array_equal(refused.valid[1:], [True] * (len(profiles) - 1))
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    evidence(
        "protein-packet-cpu-stable-provider",
        dict(
            valid=np.asarray(actual.valid),
            invalid_valid=np.asarray(refused.valid),
            packet_generated=np.asarray(actual.packet_generated),
            maximum_error_fraction=0.0,
            exact_real_host_packets=True,
            profiles=profiles,
            compiled_scope=(
                "real stable sampler+owned packet+deterministic proposal; no full work/drive fusion"
            ),
        ),
    )
    write_real_provider()


def reduced_sources():
    spec, point, _, _ = minimal_source()
    args = arguments(spec, reverse=True)
    args["membrane_thickness_m"] = {
        row.id: 2.0 ** (-28 - i) for i, row in enumerate(spec.model.membranes)
    }
    binding = units.bind_tissue(spec, **args)
    base = component_state(binding)
    sources = [
        make_source(spec, binding, base, "stable", profile) for profile in ("normal", "zero")
    ]
    encoded = [provider.encode_source(s, binding) for s in sources]
    batch = jax.tree.map(lambda *a: np.stack(a), *[e.source for e in encoded])
    return spec, point, binding, sources, batch, encoded[0].geometry


def boundary_path():
    folder = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if not folder:
        pytest.skip("Bounded qualification provides retained real compiled packets")
    return Path(folder) / "tissue-step/protein-packet-real-compiled-provider.npz"


def write_real_provider():
    _, _, _, _, batch, geometry = reduced_sources()
    g = jax.tree.map(jnp.asarray, geometry)
    compiled = jax.jit(jax.vmap(lambda source: provider.stable_packet_arrays(source, g)))
    result = compiled(jax.tree.map(jnp.asarray, batch))
    result.valid.block_until_ready()
    np.testing.assert_array_equal(result.valid, [True, True])
    leaves = jax.tree.leaves(jax.tree.map(np.asarray, (batch, geometry, result)))
    path = boundary_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **{f"leaf{i:04d}": a for i, a in enumerate(leaves)})
    metadata = dict(
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        leaf_count=len(leaves),
        source_sha256=hashlib.sha256(Path(provider.__file__).read_bytes()).hexdigest(),
        shapes=[list(a.shape) for a in leaves],
        dtypes=[a.dtype.str for a in leaves],
        threefry_partitionable=bool(jax.config.jax_threefry_partitionable),
        actual_frozen_sampler=True,
        loop_commit=False,
    )
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")


def test_cpu_jax_real_provider_to_associated_drive_gate():
    spec, point, binding, sources, batch, geometry = reduced_sources()
    templates = []
    t = provider.transition
    for source in sources:
        encoded = provider.encode_source(source, binding)
        s = encoded.source
        successor = s.stream._replace(next_tick=s.stream.next_tick + np.uint64(1))
        packet = t.SuppliedPacket(
            np.asarray(True),
            np.full(geometry.kernel.owner.shape, 0.5),
            np.asarray(1, np.int32),
            geometry.kernel.membrane_tokens,
            s.stream,
            successor,
        )
        proposal = t.propose(s, packet, geometry, **encoded.configuration, xp=np)
        templates.append(
            provider.StableProvidedPacket(
                np.asarray(True),
                np.asarray(True),
                np.asarray(True),
                packet,
                proposal,
                dict(
                    source_preflight=np.asarray(True), associated_sampled_proposal=np.asarray(True)
                ),
            )
        )
    template = (batch, geometry, jax.tree.map(lambda *a: np.stack(a), *templates))
    path = boundary_path()
    metadata = json.loads(path.with_suffix(".json").read_text())
    assert metadata["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert (
        metadata["source_sha256"]
        == hashlib.sha256(Path(provider.__file__).read_bytes()).hexdigest()
    )
    with np.load(path, allow_pickle=False) as archive:
        leaves = [np.array(archive[f"leaf{i:04d}"]) for i in range(metadata["leaf_count"])]
    assert [list(a.shape) for a in leaves] == metadata["shapes"]
    assert [a.dtype.str for a in leaves] == metadata["dtypes"]
    actual_batch, actual_geometry, provided = jax.tree.structure(template).unflatten(leaves)
    assert bool(t._equal(actual_batch, batch, xp=np)) and bool(
        t._equal(actual_geometry, geometry, xp=np)
    )
    packets = provided.packet
    proposals = provided.proposal
    field_pairs = []
    budgets = []
    expected = []
    for i, host in enumerate(sources):
        source = jax.tree.map(lambda a, world=i: np.asarray(a[world]), actual_batch)
        packet = jax.tree.map(lambda a, world=i: np.asarray(a[world]), packets)
        proposal = jax.tree.map(lambda a, world=i: np.asarray(a[world]), proposals)
        replay = reference.provide(
            units.binding_record(binding),
            provider.source_record(host),
            threefry_partitionable=metadata["threefry_partitionable"],
        )
        np.testing.assert_array_equal(packet.values, replay["packet"]["values"])
        before = replace(host, diffusion=proposal.trial.diffusion)
        after = replace(
            host,
            protein=proposal.trial.protein,
            diffusion=proposal.trial.diffusion,
            stream=replace(host.stream, next_tick=int(proposal.trial.stream.next_tick)),
            time_s=float(proposal.trial.time_s),
            loop_calls=int(proposal.trial.loop_calls),
        )
        b, e, _, _, implementation = prepare(spec, point, binding, before, before, after)
        params = frame(spec) | dict(implementation=implementation)
        conditional = t.drive.endpoint_work.evaluate(
            source.protein,
            source.protein,
            after.protein,
            b,
            e,
            geometry.work_geometry,
            **params,
            xp=np,
        )
        external = float(conditional.conditional_reversible_work_pJ)
        budgets.append(external)
        field_pairs.append((b[3:], e[3:]))
        expected.append(
            t._finish(
                source,
                packet,
                geometry,
                proposal,
                source.protein,
                b,
                e,
                **params,
                external_work_pJ=external,
                dissipated_free_energy_pJ=0.0,
                budget_provenance=PROVENANCE,
                xp=np,
            )
        )
    shared = jax.tree.map(jnp.asarray, (b.source_state, b.source_control, b.runtime_layout))
    fields = jax.tree.map(lambda *a: jnp.stack(a), *field_pairs)
    g = jax.tree.map(jnp.asarray, geometry)

    def finish(source, packet, proposal, b, e, external):
        first = t.drive.endpoint_work.endpoints.ArrayEndpoint(*shared, *b)
        last = t.drive.endpoint_work.endpoints.ArrayEndpoint(*shared, *e)
        answer = t._finish(
            source,
            packet,
            g,
            proposal,
            source.protein,
            first,
            last,
            **params,
            external_work_pJ=external,
            dissipated_free_energy_pJ=0.0,
            budget_provenance=PROVENANCE,
            xp=jnp,
        )
        work = answer.declared_drive.conditional_work
        return dict(
            valid=answer.valid,
            checks=answer.checks,
            balance=answer.declared_drive.energy_balance,
            chemical=work.chemical.total_free_energy_change_pJ,
            capacitor=work.electrical.capacitor_energy_change_pJ,
            clamp=work.electrical.clamp_work_pJ,
        )

    compiled = jax.jit(jax.vmap(finish))
    arguments = jax.tree.map(jnp.asarray, (actual_batch, packets, proposals))
    result = compiled(*arguments, *fields, jnp.asarray(budgets))
    result["valid"].block_until_ready()
    np.testing.assert_array_equal(result["valid"], [True, True])
    bad = arguments[1]._replace(values=arguments[1].values.at[0, 0].set(0.25))
    refused = compiled(arguments[0], bad, arguments[2], *fields, jnp.asarray(budgets))
    refused["valid"].block_until_ready()
    np.testing.assert_array_equal(refused["valid"], [False, True])
    error = max(
        abs(
            float(result["balance"].balance_residual_pJ[i])
            - x.declared_drive.energy_balance.balance_residual_pJ
        )
        / (3e-14 + 3e-10 * abs(x.declared_drive.energy_balance.balance_residual_pJ))
        for i, x in enumerate(expected)
    )
    host_error = max(
        ulp_error(
            result["balance"].balance_residual_pJ[i],
            host_residual(
                result["chemical"][i], result["capacitor"][i], result["clamp"][i], budgets[i], 0.0
            ),
        )
        for i in range(2)
    )
    evidence(
        "protein-packet-cpu-linked-drive",
        dict(
            valid=np.asarray(result["valid"]),
            invalid_valid=np.asarray(refused["valid"]),
            maximum_error_fraction=error,
            host_arithmetic_error_fraction=host_error,
            real_provider_sha256=metadata["sha256"],
            compiled_scope=(
                "real stable provider and source-associated passive drive gate "
                "in separate processes; selected admission/energy outputs"
            ),
        ),
    )
    assert error <= 1 and host_error <= 1
