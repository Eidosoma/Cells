"""Supplied-packet laws, complete associations and conditional energy admission."""

import ast
import hashlib
import json
import os
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import physiology_perturbation_phases as phases
from cells.core import physiology_perturbation_step as step
from cells.core import physiology_random_streams as streams
from cells.core import physiology_tissue_binding as units
from cells.numerics import physiology_protein_transition_arrays as arrays
from cells.processes import betse_perturbations as perturb
from tests.integration.test_physiology_protein_charge_view import changed_protein
from tests.unit.test_physiology_protein_drive_arrays import (
    PROVENANCE,
    host_residual,
    minimal_source,
    ulp_error,
)
from tests.unit.test_physiology_protein_electrical_arrays import prepare, two_clamps
from tests.unit.test_physiology_protein_interval_accounting import evidence
from tests.unit.test_physiology_protein_work_arrays import frame, geometry
from tests.unit.test_physiology_tissue_binding import arguments, component_state
from tests.unit.test_physiology_tissue_step import KINDS, case, control, tissue
from validation.tissue import physiology_protein_chemical_arrays_reference as chemical_reference
from validation.tissue import physiology_protein_transition_arrays_reference as reference

LAWS = dict(native=perturb.NATIVE_RNG_ID, stable=perturb.STABLE_RNG_ID)
STREAM_ID = "array-protein"


def plain(value):
    if hasattr(value, "_asdict"):
        return {key: plain(v) for key, v in value._asdict().items()}
    if isinstance(value, dict):
        return {key: plain(v) for key, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def token(text, *, digest=False):
    raw = bytes.fromhex(text) if digest else hashlib.sha256(text.encode()).digest()
    return np.frombuffer(raw, dtype="<u4").astype(np.uint32)


def configuration(law):
    return dict(
        rng_law=LAWS[law],
        native_numpy_version=np.__version__ if law == "native" else "",
        environment_mode="matrix",
    )


def component(binding, base, dt, law, profile="normal", *, tiny_density=None):
    k = binding.component.kernel
    scale = max(
        np.max(np.sum(abs(k.cell_surface_map), axis=1) / k.cell_volume_m3),
        np.max(np.sum(abs(k.environment_surface_map), axis=1) / k.environment_effective_volume_m3),
    )
    level = 2e-5 / (dt * scale)
    stock, exterior = (2.0**-10, 3 * 2.0**-10) if tiny_density is None else (2.0**-40, 2.0**-40)
    protein = perturb.ProteinState(
        np.full(k.cell_volume_m3.shape, stock),
        np.full(k.owner.shape, 1e99),
        np.full(k.environment_effective_volume_m3.shape, exterior),
    )
    diffusion = base.diffusion._replace(scheduled_m2_s=-0.125 * base.diffusion.base_m2_s)
    values = np.resize(np.array([0.125, 0.875, 0.25, 0.625]), k.owner.size)
    if law == "stable":
        values += 2.0**-53
    if tiny_density is not None:
        # Select a membrane on physical cell0 (2pL), keeping its 1:2 exterior
        # volume ratio exact. Dyadic concentration changes then resolve cleanly.
        at = next(i for i, owner in enumerate(k.owner) if binding.cell_to_tissue[owner] == 0)
        values[:] = 0.5
        values[at] = 0.75
        level = tiny_density * k.cell_volume_m3[k.owner[at]] / (0.25 * k.membrane_area_m2[at] * dt)
    flags = dict(phase=1, solver=0, dynamic_enabled=True, protein_enabled=True)
    flags.update(
        dict(
            INIT=dict(phase=0),
            fast=dict(solver=1),
            dynamic_off=dict(dynamic_enabled=False),
            protein_off=dict(protein_enabled=False),
        ).get(profile, {})
    )
    if profile == "zero":
        level = 0.0
    if profile == "negative":
        level = -level
    controls = arrays.ArrayControls(
        np.asarray(flags["phase"], np.int32),
        np.asarray(flags["solver"], np.int32),
        np.asarray(flags["dynamic_enabled"]),
        np.asarray(flags["protein_enabled"]),
        np.asarray(2.0),
        np.asarray(level),
        np.asarray(dt),
    )
    rng = (
        arrays.NativeRNGState(
            np.arange(1, 625, dtype=np.uint32),
            np.asarray(32, np.uint32),
            np.asarray(1, np.uint32),
            np.asarray(0.375),
        )
        if law == "native"
        else arrays.StableRNGState(np.asarray(17, np.uint32))
    )
    stream = arrays.ArrayStream(
        token(STREAM_ID),
        token(binding.component.identity, digest=True),
        np.asarray(2**40 + 7, np.uint64),
        np.asarray(2**40 + 31, np.uint64),
        rng,
    )
    state = arrays.ArrayComponentState(
        protein, diffusion, stream, controls, np.asarray(0.0), np.asarray(0, np.uint64)
    )
    active = bool(
        flags["phase"] == 1
        and flags["solver"] == 0
        and flags["dynamic_enabled"]
        and flags["protein_enabled"]
    )
    after_rng = (
        rng._replace(position=np.asarray(32 + 2 * k.owner.size, np.uint32))
        if law == "native" and active
        else rng
    )
    successor = stream._replace(next_tick=stream.next_tick + np.uint64(active), rng=after_rng)
    packet = arrays.SuppliedPacket(
        np.asarray(active),
        values if active else np.zeros_like(values),
        np.asarray(1, np.int32),
        k.membrane_tokens,
        stream,
        successor,
    )
    g = arrays.TransitionGeometry(
        geometry(binding),
        k,
        binding.ion_to_tissue,
        binding.membrane_thickness_m,
        token(binding.component.identity, digest=True),
    )
    return state, packet, g


def host_state(state, binding):
    r, s, c = state.stream.rng, state.stream, state.controls
    rng = (
        perturb._native_stream(
            [
                "MT19937",
                r.words.tolist(),
                int(r.position),
                int(r.has_gauss),
                float(r.cached_gaussian),
            ],
            np.__version__,
        )
        if type(r) is arrays.NativeRNGState
        else perturb.StableCoordinates(int(r.seed), int(s.world_id))
    )
    stream = streams.new_stream(
        binding.component,
        rng,
        stream_id=STREAM_ID,
        world_id=int(s.world_id),
        next_tick=int(s.next_tick),
    )
    controls = perturb.Controls(
        ("INIT", "SIM")[int(c.phase)],
        ("normal", "fast")[int(c.solver)],
        bool(c.dynamic_enabled),
        bool(c.protein_enabled),
        float(c.static_level),
        float(c.dynamic_level_mol_m2_s),
        float(c.dt_s),
    )
    return step.PhysiologyPerturbationState(
        state.protein, state.diffusion, stream, controls, float(state.time_s), int(state.loop_calls)
    )


@lru_cache(maxsize=1)
def host_law():
    path = Path(__file__).resolve().parents[2] / "src/cells/core/physiology_protein_transition.py"
    node = next(
        n
        for n in ast.parse(path.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "_component_law"
    )
    namespace = dict(component_step=step, perturb=perturb, np=np, json=json)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_component_law"]


def host_check(source, packet, proposal, binding):
    before, after = host_state(source, binding), host_state(proposal.trial, binding)
    held = (
        replace(before, diffusion=perturb.finalize_scheduled(before.diffusion, xp=np))
        if before.controls.phase == "SIM"
        else before
    )
    draw = None
    if bool(packet.present):
        provenance = (
            dict(
                rng_id=LAWS["native"],
                before_identity=before.stream.rng.identity,
                after_identity=after.stream.rng.identity,
                numpy_version=np.__version__,
            )
            if type(before.stream.rng) is perturb.NativeStream
            else dict(
                rng_id=LAWS["stable"],
                seed=before.stream.rng.seed,
                world_id=before.stream.world_id,
                tick=before.stream.next_tick,
            )
        )
        draw = perturb.prescribed_draw(
            "protein_flux",
            before.stream.next_tick,
            packet.values,
            binding.component,
            provenance=provenance,
        )
    transition = step.PerturbationTransition(after, draw, {})
    host_law()(SimpleNamespace(source_state=before, held_state=held), transition, binding.component)
    return held, after


def prepared(
    spec,
    point,
    binding,
    base,
    law,
    profile="normal",
    *,
    valence=-1.0,
    tiny_density=None,
    standard=1.0,
):
    source, packet, g = component(
        binding, base, spec.execution.dt, law, profile, tiny_density=tiny_density
    )
    proposal = arrays.propose(source, packet, g, **configuration(law), xp=np)
    before = host_state(source, binding)
    before = replace(before, diffusion=proposal.trial.diffusion)
    after = host_state(proposal.trial, binding)
    anchor = before if tiny_density is not None else changed_protein(binding, before)
    b, e, _, _, implementation = prepare(
        spec, point, binding, anchor, before, after, valence=valence
    )
    params = frame(spec, valence=valence, standard=standard) | dict(implementation=implementation)
    return source, packet, g, proposal, anchor.protein, b, e, params


def compare(name, spec, point, binding, data, law, *, expected_valid=True, strong_tiny=False):
    source, packet, g, proposal, anchor, b, e, params = data
    original = jax.tree.map(lambda a: a.tobytes(), (source, packet, g, b, e))
    if proposal.valid:
        host_check(source, packet, proposal, binding)
    conditional = arrays.drive.endpoint_work.evaluate(
        anchor, source.protein, proposal.trial.protein, b, e, g.work_geometry, **params, xp=np
    )
    dissipated = 0.0
    external = float(conditional.conditional_reversible_work_pJ)
    budgets = dict(
        external_work_pJ=external,
        dissipated_free_energy_pJ=dissipated,
        budget_provenance=PROVENANCE,
    )
    actual = arrays.evaluate(
        source, packet, g, anchor, b, e, **configuration(law), **params, **budgets, xp=np
    )
    declaration = dict(
        raw=spec.to_dict(),
        state=point.state._asdict(),
        binding=units.binding_record(binding),
        held_control=control(spec, point.time)._asdict(),
        charge_reference=anchor._asdict(),
        source=plain(source),
        packet=plain(packet),
        **frame(spec, valence=params["valence"], standard=params["standard_concentration_mol_m3"]),
        **budgets,
    )
    target = reference.evaluate(**declaration)
    errors = {}
    for field in ("cell_mol_m3", "membrane_mol_m3", "environment_mol_m3"):
        value, wanted = (
            getattr(actual.component.trial.protein, field),
            np.asarray(target["component"]["trial"]["protein"][field]),
        )
        budget = 3e-14 * abs(wanted) + 4 * abs(np.spacing(wanted))
        errors[field] = float(
            np.max(
                np.divide(abs(value - wanted), budget, out=np.zeros_like(value), where=budget > 0),
                initial=0,
            )
        )
    gross = sum(
        np.sum(np.abs(target["component"][field]))
        for field in ("requested_cell_amount_change_mol", "requested_environment_amount_change_mol")
    )
    for field in ("requested_cell_amount_change_mol", "requested_environment_amount_change_mol"):
        value, wanted = getattr(actual.component, field), np.asarray(target["component"][field])
        budget = 3e-13 * gross + 4 * abs(np.spacing(wanted))
        errors[field] = float(np.max(abs(value - wanted) / budget, initial=0))
    residual = actual.declared_drive.energy_balance.balance_residual_pJ
    desired = target["declared_drive"]["direct_SI_residual_pJ"]
    errors["SI_energy"] = abs(residual - desired) / (3e-14 + 3e-10 * abs(desired))
    if strong_tiny:
        _, fraction = chemical_reference.precision(
            actual.declared_drive.conditional_work.chemical.total_free_energy_change_pJ,
            target["declared_drive"]["conditional_work"]["chemical_energy_change_pJ"],
        )
        errors["tiny_chemical_relative"] = float(fraction)
    evidence(
        "protein-transition-arrays-" + name,
        dict(
            inputs=declaration,
            actual=plain(actual),
            expected=target,
            errors=errors,
            maximum_error_fraction=max(errors.values()),
            expected_valid=expected_valid,
            rng_law=LAWS[law],
            rng_sampler_credit=False,
        ),
    )
    assert max(errors.values()) <= 1, errors
    assert bool(actual.valid) == expected_valid, (
        actual.checks,
        actual.component.checks,
        actual.declared_drive.checks,
    )
    assert not actual.valid or target["declared_drive"]["valid"]
    assert actual.component.trial.loop_calls == source.loop_calls + np.uint64(1)
    assert actual.component.trial.time_s == float(source.time_s) + float(source.controls.dt_s)
    assert original == jax.tree.map(lambda a: a.tobytes(), (source, packet, g, b, e))
    return actual


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("law", ("native", "stable"))
@pytest.mark.parametrize("at_event", (False, True))
def test_complete_initial_evolved_prescribed_packet_laws_and_energy(kind, law, at_event):
    spec, point, binding, base, _ = case(kind, at_event=at_event, source_dt_scale=0.5)
    for stage in range(2):
        data = prepared(spec, point, binding, base, law)
        compare(
            kind + "-" + law + "-" + str(at_event) + "-" + str(stage),
            spec,
            point,
            binding,
            data,
            law,
        )
        if stage == 0:
            held = host_state(data[0]._replace(diffusion=data[3].trial.diffusion), binding)
            for _ in range(2 if at_event else 1):
                point = tissue.advance(spec, point, binding, held).checkpoint


@pytest.mark.parametrize("law", ("native", "stable"))
@pytest.mark.parametrize(
    "profile", ("INIT", "fast", "dynamic_off", "protein_off", "zero", "negative")
)
def test_source_guards_full_duration_and_zero_level_packet_semantics(law, profile):
    spec, point, binding, base, _ = case(source_dt_scale=0.5)
    data = prepared(spec, point, binding, base, law, profile)
    actual = compare("guard-" + law + "-" + profile, spec, point, binding, data, law)
    active = profile in ("zero", "negative")
    assert bool(actual.component.packet_applied) == active
    assert actual.component.trial.stream.next_tick == data[0].stream.next_tick + np.uint64(active)
    if profile == "zero":
        assert np.all(
            actual.component.trial.protein.membrane_mol_m3 != data[0].protein.membrane_mol_m3
        )
        assert np.all(actual.component.trial.protein.cell_mol_m3 == data[0].protein.cell_mol_m3)
    elif not active:
        np.testing.assert_array_equal(
            actual.component.trial.protein.membrane_mol_m3, data[0].protein.membrane_mol_m3
        )


@pytest.mark.parametrize("law", ("native", "stable"))
def test_supplied_packets_retain_unequal_clamps_and_gauge_shifts(law):
    values = []
    for shift in (0.0, 0.017):
        spec, point, binding, base = two_clamps(True, shift)
        data = prepared(spec, point, binding, base, law)
        values.append(compare("clamps-" + law + "-" + str(shift), spec, point, binding, data, law))
    first, last = (v.declared_drive.conditional_work for v in values)
    np.testing.assert_allclose(
        last.conditional_reversible_work_pJ - first.conditional_reversible_work_pJ,
        1e12 * 0.017 * first.electrical.gauge_work_coefficient_C,
        rtol=3e-10,
        atol=3e-14,
    )


@pytest.mark.parametrize("power", (70, 100))
@pytest.mark.parametrize("valence", (0.0, -1.0))
def test_tiny_packet_transfer_resolves_or_refuses_without_repair(power, valence):
    spec, point, binding, base, _ = case(source_dt_scale=0.5)
    data = prepared(
        spec,
        point,
        binding,
        base,
        "native",
        tiny_density=2.0**-power,
        valence=valence,
        standard=2.0**-40,
    )
    actual = compare(
        "tiny-" + str(power) + "-" + str(valence),
        spec,
        point,
        binding,
        data,
        "native",
        expected_valid=power == 70 and valence == 0,
        strong_tiny=power == 70 and valence == 0,
    )
    assert np.any(actual.component.requested_cell_amount_change_mol != 0)
    if power == 100:
        assert not actual.component.checks["precision/stock_response"]
    else:
        assert actual.component.valid


@pytest.mark.parametrize(
    "edit",
    (
        "site",
        "owner",
        "source_tick",
        "world",
        "packet_guard",
        "cache",
        "cache_sign",
        "cache_subnormal",
        "position",
        "words",
    ),
)
def test_native_packet_full_source_successor_and_cache_association(edit):
    _, _, binding, base, _ = case(source_dt_scale=0.5)
    s, p, g = component(binding, base, 0.002, "native")
    if edit in ("cache_sign", "cache_subnormal"):
        s = s._replace(
            stream=s.stream._replace(
                rng=s.stream.rng._replace(
                    cached_gaussian=np.asarray(0.0 if edit == "cache_sign" else 1e-310)
                )
            )
        )
        p = p._replace(
            source_stream=s.stream,
            successor_stream=p.successor_stream._replace(
                rng=p.successor_stream.rng._replace(
                    cached_gaussian=np.asarray(-0.0 if edit == "cache_sign" else 0.0)
                )
            ),
        )
    elif edit == "site":
        p = p._replace(site=np.asarray(0, np.int32))
    elif edit == "owner":
        p = p._replace(owner_tokens=p.owner_tokens[::-1])
    elif edit == "source_tick":
        p = p._replace(
            source_stream=p.source_stream._replace(
                next_tick=p.source_stream.next_tick + np.uint64(1)
            )
        )
    elif edit == "world":
        p = p._replace(
            successor_stream=p.successor_stream._replace(
                world_id=p.successor_stream.world_id + np.uint64(1)
            )
        )
    elif edit == "packet_guard":
        p = p._replace(present=np.asarray(False))
    else:
        rng = p.successor_stream.rng
        if edit == "cache":
            rng = rng._replace(cached_gaussian=np.asarray(0.25))
        elif edit == "position":
            rng = rng._replace(position=rng.position + np.uint32(1))
        else:
            rng = rng._replace(words=rng.words ^ np.uint32(1))
        p = p._replace(successor_stream=p.successor_stream._replace(rng=rng))
    actual = arrays.propose(s, p, g, **configuration("native"), xp=np)
    assert not actual.valid


@pytest.mark.parametrize(
    "profile",
    (
        "loop_max",
        "time_resolution",
        "tick_max",
        "inactive_tick_max",
        "subnormal_level",
        "source_product_underflow",
    ),
)
def test_clock_counter_and_unresolved_source_precision(profile):
    _, _, binding, base, _ = case(source_dt_scale=0.5)
    s, p, g = component(
        binding, base, 0.002, "stable", "fast" if profile == "inactive_tick_max" else "normal"
    )
    if profile == "loop_max":
        s = s._replace(loop_calls=np.asarray(2**64 - 1, np.uint64))
    elif profile == "time_resolution":
        s = s._replace(time_s=np.asarray(2.0**80))
    elif "tick_max" in profile:
        stream = s.stream._replace(next_tick=np.asarray(2**64 - 1, np.uint64))
        s = s._replace(stream=stream)
        p = p._replace(
            source_stream=stream,
            successor_stream=p.successor_stream._replace(
                next_tick=np.asarray(2**64 - 1 if profile == "inactive_tick_max" else 0, np.uint64)
            ),
        )
    else:
        s = s._replace(
            controls=s.controls._replace(
                dynamic_level_mol_m2_s=np.asarray(
                    1e-310 if profile == "subnormal_level" else np.finfo(np.float64).tiny
                )
            )
        )
    with np.errstate(all="ignore"):
        actual = arrays.propose(s, p, g, **configuration("stable"), xp=np)
    assert bool(actual.valid) == (profile == "inactive_tick_max"), actual.checks


@pytest.mark.parametrize(
    "edit",
    (
        "surface_map",
        "volume",
        "owner",
        "held_base",
        "thickness",
        "ion_map",
        "packet",
        "packet_alias",
        "clock_alias",
        "source_clock",
    ),
)
def test_full_or_guarded_gate_refuses_stale_component_geometry_permeability_and_provider(edit):
    spec, point, binding, base, _ = case(source_dt_scale=0.5)
    s, p, g, proposal, anchor, b, e, params = prepared(spec, point, binding, base, "stable")
    if edit in ("packet", "source_clock", "packet_alias", "clock_alias"):
        if edit == "packet_alias":
            p.values[0] = 0.25
        elif edit == "clock_alias":
            s.time_s[...] = 3.0
        elif edit == "packet":
            p = p._replace(values=p.values[::-1])
        else:
            s = s._replace(time_s=np.asarray(3.0))
        actual = arrays._finish(
            s,
            p,
            g,
            proposal,
            anchor,
            b,
            e,
            **params,
            external_work_pJ=0.0,
            dissipated_free_energy_pJ=0.0,
            budget_provenance=PROVENANCE,
            xp=np,
        )
        assert not actual.checks["component_source_association"]
    else:
        if edit == "surface_map":
            g = g._replace(
                kernel=g.kernel._replace(
                    environment_surface_map=g.kernel.environment_surface_map * 0.99
                )
            )
        elif edit == "volume":
            g = g._replace(kernel=g.kernel._replace(cell_volume_m3=g.kernel.cell_volume_m3 * 2))
        elif edit == "owner":
            g = g._replace(kernel=g.kernel._replace(owner=np.full_like(g.kernel.owner, 999)))
        elif edit == "held_base":
            s = s._replace(diffusion=s.diffusion._replace(base_m2_s=s.diffusion.base_m2_s * 1.2))
        elif edit == "thickness":
            g = g._replace(membrane_thickness_m=g.membrane_thickness_m * 2)
        else:
            g = g._replace(ion_to_tissue=g.ion_to_tissue[::-1])
        actual = arrays.evaluate(
            s,
            p,
            g,
            anchor,
            b,
            e,
            **configuration("stable"),
            **params,
            external_work_pJ=0.0,
            dissipated_free_energy_pJ=0.0,
            budget_provenance=PROVENANCE,
            xp=np,
        )
    assert not actual.valid


def test_no_sampler_field_solve_or_component_commit_is_called(monkeypatch):
    spec, point, binding, base, _ = case(source_dt_scale=0.5)
    data = prepared(spec, point, binding, base, "native", "zero")

    def forbidden(*a, **kw):
        raise AssertionError("No RNG/field solve/commit belongs in deterministic transition")

    for mod, name in (
        (streams, "draw"),
        (perturb, "sample_native"),
        (perturb, "sample_stable"),
        (step, "advance"),
        (phases, "finish"),
        (np.random, "RandomState"),
        (arrays.drive.endpoint_work.endpoints, "endpoint_values"),
    ):
        monkeypatch.setattr(mod, name, forbidden)
    compare("no-hidden-draw", spec, point, binding, data, "native")


@pytest.mark.parametrize("budget", ("negative_D", "unbalanced_W"))
def test_valid_component_does_not_override_a_rejected_drive_declaration(budget):
    spec, point, binding, base, _ = case(source_dt_scale=0.5)
    source, packet, geometry, proposal, anchor, before, after, params = prepared(
        spec, point, binding, base, "stable"
    )
    conditional = arrays.drive.endpoint_work.evaluate(
        anchor,
        source.protein,
        proposal.trial.protein,
        before,
        after,
        geometry.work_geometry,
        **params,
        xp=np,
    )
    dissipated = -1e-5 if budget == "negative_D" else 0.0
    external = float(conditional.conditional_reversible_work_pJ) + (
        dissipated if budget == "negative_D" else 1e-3
    )
    result = arrays.evaluate(
        source,
        packet,
        geometry,
        anchor,
        before,
        after,
        **configuration("stable"),
        **params,
        external_work_pJ=external,
        dissipated_free_energy_pJ=dissipated,
        budget_provenance=PROVENANCE,
        xp=np,
    )
    assert result.component.valid and not result.valid
    assert not result.checks["associated_declared_drive"]


@pytest.mark.parametrize("law", ("native", "stable"))
def test_cpu_jax_component_all_guards_and_invalid_worlds(law):
    _, _, binding, base, _ = case(source_dt_scale=0.5)
    profiles = ("normal", "INIT", "fast", "dynamic_off", "protein_off", "zero", "negative")
    triples = [component(binding, base, 0.002, law, profile) for profile in profiles]
    g = jax.tree.map(jnp.asarray, triples[0][2])
    batch = jax.tree.map(lambda *v: jnp.stack(v), *[(s, p) for s, p, _ in triples])
    expected = [arrays.propose(s, p, gg, **configuration(law), xp=np) for s, p, gg in triples]
    compiled = jax.jit(jax.vmap(lambda s, p: arrays.propose(s, p, g, **configuration(law), xp=jnp)))
    actual = compiled(*batch)
    actual.valid.block_until_ready()
    np.testing.assert_array_equal(actual.valid, [True] * len(profiles))
    error = 0.0
    for i, target in enumerate(expected):
        for field in arrays.perturb.ProteinState._fields:
            value, wanted = (
                np.asarray(getattr(actual.trial.protein, field)[i]),
                getattr(target.trial.protein, field),
            )
            error = max(
                error,
                float(
                    np.max(
                        abs(value - wanted) / (3e-14 * abs(wanted) + 4 * abs(np.spacing(wanted))),
                        initial=0,
                    )
                ),
            )
        np.testing.assert_array_equal(
            np.asarray(actual.trial.stream.next_tick[i]), target.trial.stream.next_tick
        )
        for aa, bb in zip(
            jax.tree.leaves(
                jax.tree.map(lambda a, world=i: np.asarray(a[world]), actual.trial.stream.rng)
            ),
            jax.tree.leaves(target.trial.stream.rng),
            strict=True,
        ):
            np.testing.assert_array_equal(aa, bb)
    bad = batch[0]._replace(
        controls=batch[0].controls._replace(phase=batch[0].controls.phase.at[0].set(2))
    )
    refused = compiled(bad, batch[1])
    refused.valid.block_until_ready()
    np.testing.assert_array_equal(refused.valid, [False] + [True] * (len(profiles) - 1))
    cache_valid = None
    if law == "native":
        cache = jnp.asarray(np.full(len(profiles), 1e-310, dtype=np.float64))
        source_cache = batch[0]._replace(
            stream=batch[0].stream._replace(rng=batch[0].stream.rng._replace(cached_gaussian=cache))
        )
        packet_cache = batch[1]._replace(
            source_stream=batch[1].source_stream._replace(
                rng=batch[1].source_stream.rng._replace(cached_gaussian=cache)
            ),
            successor_stream=batch[1].successor_stream._replace(
                rng=batch[1].successor_stream.rng._replace(cached_gaussian=cache.at[0].set(0.0))
            ),
        )
        cache_result = compiled(source_cache, packet_cache)
        cache_result.valid.block_until_ready()
        cache_valid = np.asarray(cache_result.valid)
        np.testing.assert_array_equal(cache_valid, [False] + [True] * (len(profiles) - 1))
        np.testing.assert_array_equal(
            np.asarray(cache_result.trial.stream.rng.cached_gaussian)[1:].view(np.uint64),
            np.full(len(profiles) - 1, 1e-310).view(np.uint64),
        )
    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    evidence(
        "protein-transition-cpu-component-" + law,
        dict(
            valid=np.asarray(actual.valid),
            invalid_valid=np.asarray(refused.valid),
            maximum_error_fraction=error,
            complete_RNG_compared=True,
            subnormal_cache_valid=cache_valid,
            profiles=profiles,
            rng_sampler_credit=False,
        ),
    )
    assert error <= 1
    if law == "stable":
        write_reduced_provider()


def reduced_data():
    spec, point, _, _ = minimal_source()
    args = arguments(spec, reverse=True)
    args["membrane_thickness_m"] = {
        row.id: 2.0 ** (-28 - i) for i, row in enumerate(spec.model.membranes)
    }
    binding = units.bind_tissue(spec, **args)
    base = component_state(binding)
    pairs = []
    for profile in ("normal", "zero"):
        source, packet, geometry = component(binding, base, spec.execution.dt, "stable", profile)
        pairs.append((source, packet))
    batch = jax.tree.map(lambda *a: np.stack(a), *pairs)
    return spec, point, binding, pairs, batch, geometry


def provider_path():
    folder = os.environ.get("CELLS_COMPONENT_EVIDENCE")
    if not folder:
        pytest.skip("Bounded qualification provides shared compiled-provider artifacts")
    return Path(folder) / "tissue-step/protein-transition-compiled-provider.npz"


def write_reduced_provider():
    _, _, _, _, batch, geometry = reduced_data()
    g = jax.tree.map(jnp.asarray, geometry)
    function = jax.jit(
        jax.vmap(
            lambda source, packet: arrays.propose(
                source, packet, g, **configuration("stable"), xp=jnp
            )
        )
    )
    proposal = function(*jax.tree.map(jnp.asarray, batch))
    proposal.valid.block_until_ready()
    np.testing.assert_array_equal(proposal.valid, [True, True])
    payload = jax.tree.map(np.asarray, (batch, geometry, proposal))
    leaves = jax.tree.leaves(payload)
    path = provider_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **{f"leaf{i:04d}": v for i, v in enumerate(leaves)})
    metadata = dict(
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        leaf_count=len(leaves),
        shapes=[list(v.shape) for v in leaves],
        dtypes=[v.dtype.str for v in leaves],
        source_sha256=hashlib.sha256(Path(arrays.__file__).read_bytes()).hexdigest(),
        compiled=True,
        complete_provider_records=True,
        rng_sampler_credit=False,
    )
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")


def test_cpu_jax_guarded_transition_pipeline_rejects_stale_provider_worlds():
    spec, point, binding, pairs, np_batch, gg = reduced_data()
    template = (
        np_batch,
        gg,
        jax.tree.map(
            lambda *a: np.stack(a),
            *[arrays.propose(s, p, gg, **configuration("stable"), xp=np) for s, p in pairs],
        ),
    )
    path = provider_path()
    metadata = json.loads(path.with_suffix(".json").read_text())
    assert metadata["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert (
        metadata["source_sha256"] == hashlib.sha256(Path(arrays.__file__).read_bytes()).hexdigest()
    )
    with np.load(path, allow_pickle=False) as saved:
        assert set(saved.files) == {f"leaf{i:04d}" for i in range(metadata["leaf_count"])}
        leaves = [np.array(saved[f"leaf{i:04d}"]) for i in range(metadata["leaf_count"])]
    assert [list(v.shape) for v in leaves] == metadata["shapes"]
    assert [v.dtype.str for v in leaves] == metadata["dtypes"]
    loaded_batch, loaded_g, loaded_proposals = jax.tree.structure(template).unflatten(leaves)
    assert bool(arrays._equal(loaded_batch, np_batch, xp=np))
    assert bool(arrays._equal(loaded_g, gg, xp=np))
    batch, g, proposals = jax.tree.map(jnp.asarray, (loaded_batch, loaded_g, loaded_proposals))
    field_pairs = []
    targets = []
    budgets = []
    for i, (s, p) in enumerate(pairs):
        proposal = jax.tree.map(lambda a, world=i: np.asarray(a[world]), loaded_proposals)
        trial = proposal.trial
        first = host_state(s, binding)
        first = replace(first, diffusion=trial.diffusion)
        last = host_state(trial, binding)
        b, e, _, _, implementation = prepare(spec, point, binding, first, first, last)
        params = frame(spec) | dict(implementation=implementation)
        cond = arrays.drive.endpoint_work.evaluate(
            s.protein, s.protein, trial.protein, b, e, gg.work_geometry, **params, xp=np
        )
        budgets.append(float(cond.conditional_reversible_work_pJ))
        field_pairs.append((b[3:], e[3:]))
        targets.append(
            arrays._finish(
                s,
                p,
                gg,
                proposal,
                s.protein,
                b,
                e,
                **params,
                external_work_pJ=budgets[-1],
                dissipated_free_energy_pJ=0.0,
                budget_provenance=PROVENANCE,
                xp=np,
            )
        )
    shared = jax.tree.map(jnp.asarray, (b.source_state, b.source_control, b.runtime_layout))
    fields = jax.tree.map(lambda *a: jnp.stack(a), *field_pairs)

    def finish(s, p, proposal, b, e, external):
        first = arrays.drive.endpoint_work.endpoints.ArrayEndpoint(*shared, *b)
        last = arrays.drive.endpoint_work.endpoints.ArrayEndpoint(*shared, *e)
        result = arrays._finish(
            s,
            p,
            g,
            proposal,
            s.protein,
            first,
            last,
            **params,
            external_work_pJ=external,
            dissipated_free_energy_pJ=0.0,
            budget_provenance=PROVENANCE,
            xp=jnp,
        )
        return dict(
            valid=result.valid,
            checks=result.checks,
            balance=result.declared_drive.energy_balance,
            chemical=result.declared_drive.conditional_work.chemical.total_free_energy_change_pJ,
            capacitor=result.declared_drive.conditional_work.electrical.capacitor_energy_change_pJ,
            clamp=result.declared_drive.conditional_work.electrical.clamp_work_pJ,
        )

    compiled = jax.jit(jax.vmap(finish))
    actual = compiled(*batch, proposals, *fields, jnp.asarray(budgets))
    actual["valid"].block_until_ready()
    np.testing.assert_array_equal(actual["valid"], [True, True])
    bad = batch[1]._replace(values=batch[1].values.at[0, 0].set(0.25))
    refused = compiled(batch[0], bad, proposals, *fields, jnp.asarray(budgets))
    refused["valid"].block_until_ready()
    np.testing.assert_array_equal(refused["valid"], [False, True])
    assert not bool(refused["checks"]["component_source_association"][0])
    error = max(
        abs(
            float(actual["balance"].balance_residual_pJ[i])
            - t.declared_drive.energy_balance.balance_residual_pJ
        )
        / (3e-14 + 3e-10 * abs(t.declared_drive.energy_balance.balance_residual_pJ))
        for i, t in enumerate(targets)
    )
    host_error = max(
        ulp_error(
            actual["balance"].balance_residual_pJ[i],
            host_residual(
                actual["chemical"][i],
                actual["capacitor"][i],
                actual["clamp"][i],
                budgets[i],
                0.0,
            ),
        )
        for i in range(2)
    )
    evidence(
        "protein-transition-cpu-guarded-pipeline",
        dict(
            valid=np.asarray(actual["valid"]),
            invalid_valid=np.asarray(refused["valid"]),
            maximum_error_fraction=error,
            host_arithmetic_error_fraction=host_error,
            provider_sha256=metadata["sha256"],
            selected_outputs="complete admission checks and energy balance/components",
            compiled_scope=(
                "two compiled, source-associated stages in separate processes; "
                "reduced passive geometry; no monolithic fusion or sampler credit"
            ),
        ),
    )
    assert error <= 1
    assert host_error <= 1
