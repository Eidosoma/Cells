"""Deterministic post-ion protein proposals from supplied, owned packets.

No sampler or loop commit exists here. Complete source/successor RNG records
are supplied by the admitted packet provider. Numeric association checks do
not authenticate a tape or regenerate native/stable random values.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp

from cells.core import physiology_protein_chemical_arrays as chemical
from cells.core.physiology_perturbation_step import BALANCE_RELATIVE_TOLERANCE
from cells.numerics import physiology_protein_drive_arrays as drive
from cells.numerics.physiology_protein_interval_arrays import _barrier
from cells.processes import betse_perturbations as perturb


class ArrayControls(NamedTuple):
    phase: object  # int32: INIT0, SIM1.
    solver: object  # int32: normal0, fast1.
    dynamic_enabled: object
    protein_enabled: object
    static_level: object
    dynamic_level_mol_m2_s: object
    dt_s: object


class NativeRNGState(NamedTuple):
    words: object
    position: object
    has_gauss: object
    cached_gaussian: object


class StableRNGState(NamedTuple):
    seed: object


class ArrayStream(NamedTuple):
    stream_identity: object
    layout_identity: object
    world_id: object
    next_tick: object
    rng: object


class ArrayComponentState(NamedTuple):
    protein: object
    diffusion: object
    stream: object
    controls: object
    time_s: object
    loop_calls: object


class SuppliedPacket(NamedTuple):
    present: object
    values: object
    site: object  # int32 index of protein_flux in frozen SITES.
    owner_tokens: object
    source_stream: object
    successor_stream: object


class TransitionGeometry(NamedTuple):
    work_geometry: object
    kernel: object
    ion_to_tissue: object
    membrane_thickness_m: object
    binding_identity: object


class ProteinProposal(NamedTuple):
    valid: object
    source_state: object
    source_packet: object
    source_geometry: object
    trial: object
    active: object
    packet_applied: object
    flux_mol_m2_s: object
    requested_cell_amount_change_mol: object
    requested_environment_amount_change_mol: object
    represented_cell_amount_change_mol: object
    represented_environment_amount_change_mol: object
    requested_balance_residual_mol: object
    checks: object


class ProteinTransitionAdmission(NamedTuple):
    valid: object
    component: object
    declared_drive: object
    checks: object


def _axis(value, shape, dtype, name):
    if (
        not hasattr(value, "shape")
        or not hasattr(value, "dtype")
        or value.shape != shape
        or value.dtype != dtype
    ):
        raise ValueError("Require original " + name + " shape/dtype")


def _equal(a, b, *, xp):
    if jax.tree.structure(a) != jax.tree.structure(b):
        raise ValueError("Require complete matching source structures")
    aa, bb = jax.tree.leaves(a), jax.tree.leaves(b)
    if any(x.shape != y.shape or x.dtype != y.dtype for x, y in zip(aa, bb, strict=True)):
        raise ValueError("Require original complete source axes/dtypes")
    return xp.all(
        xp.stack(
            [
                xp.all((x == y) & (xp.signbit(x) == xp.signbit(y)))
                if x.dtype.kind == "f"
                else xp.all(x == y)
                for x, y in zip(aa, bb, strict=True)
            ]
        )
    )


def _stream(stream, rng_law, *, xp):
    if type(stream) is not ArrayStream:
        raise ValueError("Require a complete ArrayStream")
    for value, shape, dtype, name in (
        (stream.stream_identity, (8,), xp.uint32, "stream identity"),
        (stream.layout_identity, (8,), xp.uint32, "layout identity"),
        (stream.world_id, (), xp.uint64, "world id"),
        (stream.next_tick, (), xp.uint64, "logical tick"),
    ):
        _axis(value, shape, dtype, name)
    rng = stream.rng
    if rng_law == perturb.NATIVE_RNG_ID:
        if type(rng) is not NativeRNGState:
            raise ValueError("Require the complete native MT19937/cache state")
        for value, shape, dtype, name in (
            (rng.words, (624,), xp.uint32, "MT19937 words"),
            (rng.position, (), xp.uint32, "MT19937 position"),
            (rng.has_gauss, (), xp.uint32, "Gaussian cache flag"),
            (rng.cached_gaussian, (), xp.float64, "Gaussian cache value"),
        ):
            _axis(value, shape, dtype, name)
        return (
            xp.any(rng.words != 0)
            & (rng.position <= 624)
            & (rng.has_gauss <= 1)
            & xp.isfinite(rng.cached_gaussian)
        )
    if type(rng) is not StableRNGState:
        raise ValueError("Require the complete stable coordinate seed")
    _axis(rng.seed, (), xp.uint32, "stable seed")
    return xp.asarray(True)


def _geometry(g, checks, *, xp):
    if type(g) is not TransitionGeometry or type(g.kernel) is not perturb.Kernel:
        raise ValueError("Require complete TransitionGeometry and original component Kernel")
    w, k = g.work_geometry, g.kernel
    if type(w) is not drive.endpoint_work.WorkGeometry:
        raise ValueError("Require the complete frozen WorkGeometry")
    nc, no, nm = w.cell_to_tissue.size, w.environment_to_tissue.size, w.membrane_to_tissue.size
    if not nc or not no or not nm:
        raise ValueError("Require complete nonempty ordinary physical owner axes")
    for value, shape, dtype, name in (
        (k.owner, (nm,), xp.int64, "membrane cell owners"),
        (k.environment_owner, (nm,), xp.int64, "membrane environment owners"),
        (k.membrane_area_m2, (nm,), xp.float64, "membrane SI areas"),
        (k.cell_volume_m3, (nc,), xp.float64, "cell SI volumes"),
        (k.environment_effective_volume_m3, (no,), xp.float64, "environment SI volumes"),
        (k.cell_surface_map, (nc, nm), xp.float64, "cell surface map"),
        (k.environment_surface_map, (no, nm), xp.float64, "environment surface map"),
        (k.membrane_tokens, (nm, 8), xp.uint32, "membrane owner tokens"),
        (g.membrane_thickness_m, (nm,), xp.float64, "membrane SI thickness"),
        (g.binding_identity, (8,), xp.uint32, "binding identity"),
    ):
        _axis(value, shape, dtype, name)
    nb = k.boundary_categories.size
    if not 0 < nb <= nc:
        raise ValueError("Require the complete boundary occurrence categories")
    _axis(k.boundary_categories, (nb,), xp.int64, "boundary categories")
    _axis(k.boundary_cumulative_weights, (nb,), xp.int64, "boundary weights")
    checks["geometry/component_work_association"] = xp.all(
        xp.stack(
            [
                _equal(a, b, xp=xp)
                for a, b in (
                    (k.owner, w.membrane_owner),
                    (k.environment_owner, w.membrane_environment_owner),
                    (k.membrane_area_m2, w.membrane_area_m2),
                    (k.cell_volume_m3, w.cell_volume_m3),
                    (k.environment_effective_volume_m3, w.environment_volume_m3),
                )
            ]
        )
    )
    cell_map = xp.where(xp.arange(nc)[:, None] == k.owner, k.membrane_area_m2[None, :], 0.0)
    env_map = xp.where(
        xp.arange(no)[:, None] == k.environment_owner, k.membrane_area_m2[None, :], 0.0
    )
    checks["geometry/original_matrix_maps"] = xp.all(cell_map == k.cell_surface_map) & xp.all(
        env_map == k.environment_surface_map
    )
    checks["geometry/owner_domain"] = (
        xp.all((k.owner >= 0) & (k.owner < nc))
        & xp.all((k.environment_owner >= 0) & (k.environment_owner < no))
        & xp.all(xp.sum(cell_map, axis=1) > 0)
    )
    checks["geometry/domain"] = xp.all(
        xp.stack(
            [
                xp.all(xp.isfinite(value) & (value > 0) & ~chemical._subnormal(value, xp=xp))
                for value in (
                    k.membrane_area_m2,
                    k.cell_volume_m3,
                    k.environment_effective_volume_m3,
                    g.membrane_thickness_m,
                )
            ]
        )
    ) & xp.all(k.environment_effective_volume_m3 == k.environment_effective_volume_m3[0])
    distinct = xp.any(
        k.membrane_tokens[:, None, :] != k.membrane_tokens[None, :, :], axis=-1
    ) | xp.eye(nm, dtype=bool)
    categories_distinct = (
        k.boundary_categories[:, None] != k.boundary_categories[None, :]
    ) | xp.eye(nb, dtype=bool)
    checks["geometry/complete_boundary_tokens"] = (
        xp.all(distinct)
        & xp.all(categories_distinct)
        & xp.all((k.boundary_categories >= 0) & (k.boundary_categories < nc))
        & xp.all(k.boundary_cumulative_weights > 0)
        & xp.all(k.boundary_cumulative_weights[1:] > k.boundary_cumulative_weights[:-1])
    )
    return nc, no, nm


def propose(source, packet, geometry, *, rng_law, native_numpy_version, environment_mode, xp=jnp):
    """Attempt the original deterministic component update, without committing it.

    Codes encode INIT/SIM and normal/fast exactly; all guards are dynamic scalar
    arrays. An absent packet has zero values and an unchanged successor stream.
    Enabled zero-level calls require a supplied packet and advance its tick.
    Complete RNG words/cache are supplied records, never generated here.
    """
    if rng_law not in (perturb.NATIVE_RNG_ID, perturb.STABLE_RNG_ID):
        raise ValueError("Require an exact original native/stable RNG law")
    if environment_mode != "matrix":
        raise ValueError("Require the qualified ordinary matrix exterior mode")
    if native_numpy_version != (perturb.np.__version__ if rng_law == perturb.NATIVE_RNG_ID else ""):
        raise ValueError("Native packet version must match its admitted NumPy source")
    if (
        type(source) is not ArrayComponentState
        or type(source.controls) is not ArrayControls
        or type(packet) is not SuppliedPacket
    ):
        raise ValueError("Require complete component, control and supplied packet records")
    if any(
        type(s) is not ArrayStream
        for s in (source.stream, packet.source_stream, packet.successor_stream)
    ):
        raise ValueError("Require complete source and supplied packet streams")
    checks = {}
    nc, no, nm = _geometry(geometry, checks, xp=xp)
    if (
        type(source.protein) is not perturb.ProteinState
        or type(source.diffusion) is not perturb.StaticState
    ):
        raise ValueError("Require original complete protein and diffusion records")
    for value, n in zip(source.protein, (nc, nm, no), strict=True):
        _axis(value, (n,), xp.float64, "protein buffers")
    if source.diffusion.current_m2_s.ndim != 2:
        raise ValueError("Require complete ion-by-membrane diffusion axes")
    ni = source.diffusion.current_m2_s.shape[0]
    for value in source.diffusion:
        _axis(value, (ni, nm), xp.float64, "diffusion buffers")
    _axis(geometry.ion_to_tissue, (ni,), xp.int64, "ion owner map")
    checks["geometry/ion_owner_map"] = xp.all(
        xp.sum(geometry.ion_to_tissue[:, None] == xp.arange(ni)[None, :], axis=0) == 1
    )
    c = source.controls
    for value, dtype, name in (
        (c.phase, xp.int32, "phase code"),
        (c.solver, xp.int32, "solver code"),
        (c.dynamic_enabled, xp.bool_, "dynamic guard"),
        (c.protein_enabled, xp.bool_, "protein guard"),
        (c.static_level, xp.float64, "static level"),
        (c.dynamic_level_mol_m2_s, xp.float64, "dynamic level"),
        (c.dt_s, xp.float64, "component dt"),
        (source.time_s, xp.float64, "elapsed component time"),
        (source.loop_calls, xp.uint64, "component call count"),
        (packet.present, xp.bool_, "packet presence"),
        (packet.site, xp.int32, "packet site"),
    ):
        _axis(value, (), dtype, name)
    _axis(packet.values, (nm,), xp.float64, "supplied uniform values")
    _axis(packet.owner_tokens, (nm, 8), xp.uint32, "packet owner tokens")
    checks["source/buffers"] = xp.all(
        xp.stack(
            [
                xp.all(xp.isfinite(v) & (v >= 0))
                for v in (
                    *source.protein,
                    source.diffusion.current_m2_s,
                    source.diffusion.base_m2_s,
                )
            ]
        )
    ) & xp.all(xp.isfinite(source.diffusion.scheduled_m2_s))
    checks["controls/original_domain"] = (
        ((c.phase == 0) | (c.phase == 1))
        & ((c.solver == 0) | (c.solver == 1))
        & xp.all(xp.isfinite(xp.stack((c.static_level, c.dynamic_level_mol_m2_s, c.dt_s))))
        & (c.dt_s > 0)
    )
    active = (c.phase == 1) & (c.solver == 0) & c.dynamic_enabled & c.protein_enabled
    max_uint = xp.uint64(2**64 - 1)
    future_time = _barrier(source.time_s + c.dt_s, xp=xp)
    checks["clock/component_advance"] = (
        xp.isfinite(source.time_s)
        & (source.time_s >= 0)
        & xp.isfinite(future_time)
        & (future_time > source.time_s)
        & (source.loop_calls < max_uint)
        & (~active | (source.stream.next_tick < max_uint))
    )
    checks["precision/clock_dt"] = ~chemical._subnormal(c.dt_s, xp=xp)
    checks["stream/domains"] = xp.all(
        xp.stack(
            [
                _stream(s, rng_law, xp=xp)
                for s in (source.stream, packet.source_stream, packet.successor_stream)
            ]
        )
    )
    checks["packet/source_association"] = _equal(source.stream, packet.source_stream, xp=xp)
    checks["stream/binding_association"] = xp.all(
        source.stream.layout_identity == geometry.binding_identity
    )
    checks["packet/guard_and_support"] = (
        (packet.present == active)
        & (packet.site == perturb.SITES.index("protein_flux"))
        & xp.all(packet.owner_tokens == geometry.kernel.membrane_tokens)
        & xp.all(xp.isfinite(packet.values) & (packet.values >= 0) & (packet.values < 1))
        & (active | xp.all(packet.values == 0))
    )
    first, last = source.stream, packet.successor_stream
    checks["packet/successor_ownership"] = _equal(first[:3], last[:3], xp=xp) & (
        last.next_tick == first.next_tick + active.astype(xp.uint64)
    )
    if rng_law == perturb.NATIVE_RNG_ID:
        initial, final = first.rng, last.rng
        end = initial.position + xp.uint32(2 * nm)
        position = (end - xp.uint32(1)) % xp.uint32(624) + xp.uint32(1)
        cache_same = (
            (initial.has_gauss == final.has_gauss)
            & (initial.cached_gaussian == final.cached_gaussian)
            & (xp.signbit(initial.cached_gaussian) == xp.signbit(final.cached_gaussian))
        )
        no_twist_words = (end > 624) | xp.all(initial.words == final.words)
        native_update = cache_same & (final.position == position) & no_twist_words
        checks["packet/rng_successor"] = xp.where(
            active, native_update, _equal(first.rng, last.rng, xp=xp)
        )
    else:
        checks["packet/rng_successor"] = _equal(first.rng, last.rng, xp=xp)
    held_current = xp.where(
        c.phase == 1,
        _barrier(source.diffusion.base_m2_s + source.diffusion.scheduled_m2_s, xp=xp),
        source.diffusion.current_m2_s,
    )
    diffusion = perturb.StaticState(
        held_current, source.diffusion.base_m2_s, source.diffusion.scheduled_m2_s
    )
    checks["diffusion/held_domain"] = xp.all(xp.isfinite(held_current) & (held_current >= 0))
    k = geometry.kernel
    flux = xp.where(
        active,
        _barrier(c.dynamic_level_mol_m2_s * _barrier(packet.values - 0.5, xp=xp), xp=xp),
        0.0,
    )
    checks["precision/flux_response"] = ~active | (
        ~chemical._subnormal(c.dynamic_level_mol_m2_s, xp=xp)
        & xp.all((c.dynamic_level_mol_m2_s == 0) | (packet.values == 0.5) | (flux != 0))
    )
    cell_flow = _barrier(xp.einsum("ij,j->i", k.cell_surface_map, flux), xp=xp)
    env_flow = -_barrier(xp.einsum("ij,j->i", k.environment_surface_map, flux), xp=xp)
    cell_amount = _barrier(cell_flow * c.dt_s, xp=xp)
    env_amount = _barrier(env_flow * c.dt_s, xp=xp)
    surface_product = _barrier(k.membrane_area_m2 * flux, xp=xp)
    edge_amount = chemical._product((flux, k.membrane_area_m2, c.dt_s), xp=xp)
    checks["precision/source_products"] = (
        xp.all((flux == 0) | (surface_product != 0))
        & ~xp.any(chemical._subnormal(surface_product, xp=xp))
        & xp.all((cell_flow == 0) | (cell_amount != 0))
        & xp.all((env_flow == 0) | (env_amount != 0))
        & ~xp.any(edge_amount[1] | edge_amount[2])
    )
    cell = _barrier(
        source.protein.cell_mol_m3 + _barrier(cell_amount / k.cell_volume_m3, xp=xp), xp=xp
    )
    outside = _barrier(
        source.protein.environment_mol_m3
        + _barrier(env_amount / k.environment_effective_volume_m3, xp=xp),
        xp=xp,
    )
    membrane = xp.where(active, cell[xp.clip(k.owner, 0, nc - 1)], source.protein.membrane_mol_m3)
    protein = perturb.ProteinState(cell, membrane, outside)
    requested = xp.concatenate((cell_amount, env_amount))
    net, gross, rounding, _, resolved = drive.endpoint_work._balance(requested, xp=xp)
    checks["protein/requested_material"] = (
        resolved
        & xp.isfinite(net)
        & xp.isfinite(gross)
        & (xp.abs(net) + rounding <= BALANCE_RELATIVE_TOLERANCE * gross)
    )
    checks["protein/proposed_domain"] = xp.all(
        xp.stack([xp.all(xp.isfinite(v) & (v >= 0)) for v in protein])
    )
    lost = xp.any((cell_amount != 0) & (cell == source.protein.cell_mol_m3)) | xp.any(
        (env_amount != 0) & (outside == source.protein.environment_mol_m3)
    )
    checks["precision/stock_response"] = ~lost
    checks["precision/requested_amount"] = xp.all(xp.isfinite(requested)) & ~xp.any(
        chemical._subnormal(requested, xp=xp)
    )
    stream = jax.tree.map(lambda a, b: xp.where(active, b, a), source.stream, last)
    trial = ArrayComponentState(
        protein, diffusion, stream, c, future_time, source.loop_calls + xp.uint64(1)
    )
    checks = {key: checks[key] for key in sorted(checks)}
    return ProteinProposal(
        xp.all(xp.stack(tuple(checks.values()))),
        jax.tree.map(lambda a: xp.array(a, copy=True), source),
        jax.tree.map(lambda a: xp.array(a, copy=True), packet),
        jax.tree.map(lambda a: xp.array(a, copy=True), geometry),
        trial,
        active,
        active & packet.present,
        flux,
        cell_amount,
        env_amount,
        (cell - source.protein.cell_mol_m3) * k.cell_volume_m3,
        (outside - source.protein.environment_mol_m3) * k.environment_effective_volume_m3,
        xp.sum(cell_amount) + xp.sum(env_amount),
        checks,
    )


def evaluate(
    source,
    packet,
    geometry,
    charge_reference,
    before_endpoint,
    after_endpoint,
    *,
    rng_law,
    native_numpy_version,
    environment_mode,
    external_work_pJ,
    dissipated_free_energy_pJ,
    budget_provenance,
    valence,
    faraday_C_mol,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K,
    implementation,
    xp=jnp,
):
    """Admit a deterministic supplied-packet proposal against actual endpoints.

    SIM finalization was held during caller-owned ionic evolution. Check its
    exact D/thickness to P mapping now, then recompute the complete declared
    drive gate for this source/proposed protein pair. No state is committed.
    """
    proposal = propose(
        source,
        packet,
        geometry,
        rng_law=rng_law,
        native_numpy_version=native_numpy_version,
        environment_mode=environment_mode,
        xp=xp,
    )
    return _finish(
        source,
        packet,
        geometry,
        proposal,
        charge_reference,
        before_endpoint,
        after_endpoint,
        external_work_pJ=external_work_pJ,
        dissipated_free_energy_pJ=dissipated_free_energy_pJ,
        budget_provenance=budget_provenance,
        valence=valence,
        faraday_C_mol=faraday_C_mol,
        temperature_K=temperature_K,
        standard_concentration_mol_m3=standard_concentration_mol_m3,
        gas_constant_J_mol_K=gas_constant_J_mol_K,
        implementation=implementation,
        xp=xp,
    )


def _finish(
    source,
    packet,
    geometry,
    proposal,
    charge_reference,
    before_endpoint,
    after_endpoint,
    *,
    external_work_pJ,
    dissipated_free_energy_pJ,
    budget_provenance,
    valence,
    faraday_C_mol,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K,
    implementation,
    xp,
):
    """Internal guarded boundary for resource-separated compilation.

    Only the public complete-input wrapper supplies proposals for admission.
    Captured numeric source/packet/geometry association is not authentication.
    """
    if type(proposal) is not ProteinProposal:
        raise ValueError("Require the actual internal proposal-provider record")
    admission = drive.evaluate(
        charge_reference,
        source.protein,
        proposal.trial.protein,
        before_endpoint,
        after_endpoint,
        geometry.work_geometry,
        external_work_pJ=external_work_pJ,
        dissipated_free_energy_pJ=dissipated_free_energy_pJ,
        budget_provenance=budget_provenance,
        valence=valence,
        faraday_C_mol=faraday_C_mol,
        temperature_K=temperature_K,
        standard_concentration_mol_m3=standard_concentration_mol_m3,
        gas_constant_J_mol_K=gas_constant_J_mol_K,
        implementation=implementation,
        xp=xp,
    )
    p, g = before_endpoint.runtime_layout, geometry
    ni, nm = source.diffusion.current_m2_s.shape
    if ni != p.membrane_permeability.shape[0]:
        raise ValueError("Require complete component and field ion axes")
    ions = xp.clip(g.ion_to_tissue, 0, ni - 1)
    membranes = xp.clip(g.work_geometry.membrane_to_tissue, 0, p.membrane_active.size - 1)
    counts = xp.sum(g.ion_to_tissue[:, None] == xp.arange(ni)[None, :], axis=0)
    converted = proposal.trial.diffusion.current_m2_s / g.membrane_thickness_m
    observed = p.membrane_permeability[ions[:, None], membranes[None, :]]
    checks = dict(
        component_source_association=_equal(source, proposal.source_state, xp=xp)
        & _equal(packet, proposal.source_packet, xp=xp)
        & _equal(geometry, proposal.source_geometry, xp=xp),
        component_proposal=proposal.valid,
        associated_declared_drive=admission.valid,
        complete_ion_map=xp.all(counts == 1),
        held_permeability=xp.all(converted == observed)
        & xp.all(xp.where(p.membrane_active, True, p.membrane_permeability == 0)),
        SI_conversion=xp.all(xp.isfinite(converted))
        & xp.all((proposal.trial.diffusion.current_m2_s == 0) | (converted != 0)),
    )
    checks = {key: checks[key] for key in sorted(checks)}
    return ProteinTransitionAdmission(
        xp.all(xp.stack(tuple(checks.values()))), proposal, admission, checks
    )
