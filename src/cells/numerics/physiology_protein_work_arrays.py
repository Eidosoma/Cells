"""Conditional protein endpoint work from one complete numeric input contract.

The explicit owner map, SI volumes and complete protein states generate all
three charge projections. Actual field records are checked against them; no
anonymous chemical/electrical receipt is accepted. Named-source provenance and
the separate protein species declaration remain host admission responsibilities.
"""

from typing import NamedTuple

import jax.numpy as jnp

from cells.core import physiology_protein_chemical_arrays as chemical
from cells.core.physiology_perturbation_step import BALANCE_RELATIVE_TOLERANCE
from cells.numerics import physiology_protein_electrical_arrays as electrical
from cells.numerics import physiology_protein_interval_arrays as endpoints
from cells.numerics.extracellular_field import ordered_scatter
from cells.processes.betse_perturbations import ProteinState
from cells.processes.electrochemistry import F, R

EPS = 2.220446049250313e-16


class WorkGeometry(NamedTuple):
    cell_to_tissue: object
    environment_to_tissue: object
    membrane_to_tissue: object
    cell_volume_m3: object
    environment_volume_m3: object
    membrane_owner: object
    membrane_environment_owner: object
    membrane_area_m2: object


class ChargeProjection(NamedTuple):
    amount_delta_mol: object
    charge_delta_C: object
    padded_charge_delta_C: object
    amount_balance_normalized: object
    amount_gross_normalized: object
    amount_binary_exponent: object
    charge_balance_normalized: object
    charge_binary_exponent: object
    charge_tolerance_normalized: object
    charge_comparison_binary_exponent: object
    representable: object
    strict_valid: object


class ConditionalProteinWork(NamedTuple):
    valid: object
    conditional_reversible_work_pJ: object
    addition_roundoff_pJ: object
    addition_roundoff_bound_pJ: object
    component_roundoff_bound_pJ: object
    work_roundoff_bound_pJ: object
    chemical: object
    electrical: object
    before_projection: object
    after_projection: object
    requested_projection: object
    checks: object
    diagnostics: object


def _sum(value, *, xp):
    high, low = chemical._sum_pair(value.reshape(-1), xp=xp)
    return high + low


def _coverage(indices, active, *, xp):
    hits = xp.sum(indices[:, None] == xp.arange(active.size)[None, :], axis=0)
    return xp.all(hits == active.astype(xp.int64))


def _geometry(g, p, checks, *, xp):
    if type(g) is not WorkGeometry:
        raise ValueError("Require a complete numeric WorkGeometry")
    sizes = (g.cell_to_tissue.size, g.environment_to_tissue.size, g.membrane_to_tissue.size)
    nc, no, nm = sizes
    if not nc or not no or not nm:
        raise ValueError("Require the complete nonempty ordinary physical owner axes")
    for value, size in (
        (g.cell_to_tissue, nc),
        (g.environment_to_tissue, no),
        (g.membrane_to_tissue, nm),
        (g.membrane_owner, nm),
        (g.membrane_environment_owner, nm),
    ):
        if value.shape != (size,) or value.dtype != xp.int64:
            raise ValueError("Require complete one-dimensional int64 owner maps")
    for value, size in (
        (g.cell_volume_m3, nc),
        (g.environment_volume_m3, no),
        (g.membrane_area_m2, nm),
    ):
        if value.shape != (size,) or value.dtype != xp.float64:
            raise ValueError("Require float64 SI m3/m2 geometry on the component owner axes")
    for name, indices, active in (
        ("cell", g.cell_to_tissue, p.active),
        ("environment", g.environment_to_tissue, p.outside_active),
        ("membrane", g.membrane_to_tissue, p.membrane_active),
    ):
        checks["geometry/" + name + "_coverage"] = _coverage(indices, active, xp=xp)
    checks["geometry/component_membrane_owners"] = xp.all(
        (g.membrane_owner >= 0)
        & (g.membrane_owner < nc)
        & (g.membrane_environment_owner >= 0)
        & (g.membrane_environment_owner < no)
    )
    ci = xp.clip(g.cell_to_tissue, 0, p.active.size - 1)
    oi = xp.clip(g.environment_to_tissue, 0, p.outside_active.size - 1)
    mi = xp.clip(g.membrane_to_tissue, 0, p.membrane_active.size - 1)
    checks["geometry/membrane_incidence"] = xp.all(
        (p.membrane_cell[mi] == ci[xp.clip(g.membrane_owner, 0, nc - 1)])
        & (p.membrane_outside[mi] == oi[xp.clip(g.membrane_environment_owner, 0, no - 1)])
    )
    checks["geometry/SI_volumes"] = xp.all(
        g.cell_volume_m3 == endpoints._barrier(p.volume[ci] * 1e-15, xp=xp)
    ) & xp.all(
        g.environment_volume_m3 == endpoints._barrier(p.extracellular_volume[oi] * 1e-15, xp=xp)
    )
    checks["geometry/SI_area"] = xp.all(g.membrane_area_m2 == p.membrane_area[mi])
    checks["geometry/domain"] = xp.all(
        xp.stack(
            [
                xp.all(xp.isfinite(v) & (v > 0) & ~chemical._subnormal(v, xp=xp))
                for v in (g.cell_volume_m3, g.environment_volume_m3, g.membrane_area_m2)
            ]
        )
    )
    return ci, oi


def _balance(values, *, xp):
    mantissa, power = xp.frexp(values)
    scale = xp.max(xp.where(values != 0, power, -8192), initial=-8192)
    scale = xp.where(xp.any(values != 0), scale, 0)
    normalized = xp.ldexp(mantissa, power - scale)
    net = _sum(normalized, xp=xp)
    gross = _sum(xp.abs(normalized), xp=xp)
    bound = 64 * EPS * gross
    resolved = xp.all((values == 0) | (normalized != 0))
    return net, gross, bound, scale, resolved


def _quantities(concentration, volume, z, faraday, *, xp):
    # Preserve the frozen host projection's original multiplication grouping.
    amount = endpoints._barrier(concentration * volume, xp=xp)
    fmol = endpoints._barrier(amount * 1e15, xp=xp)
    charge = endpoints._barrier(endpoints._barrier(amount * z, xp=xp) * faraday, xp=xp)
    valid = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in (amount, fmol, charge)]))
    valid &= xp.all((concentration == 0) | (amount != 0))
    valid &= xp.all((amount == 0) | (z == 0) | (charge != 0))
    # Raw SI projection on subnormals is backend-dependent. Retain its numbers,
    # but do not qualify closed work from a conversion near flush-to-zero.
    valid &= ~xp.any(chemical._subnormal(amount, xp=xp) | chemical._subnormal(charge, xp=xp))
    return amount, charge, valid


def _projection(before, after, volume, ci, oi, p, z, faraday, *, xp):
    delta = endpoints._barrier(after - before, xp=xp)
    amount, charge, representable = _quantities(delta, volume, z, faraday, xp=xp)
    net, gross, bound, scale, resolved = _balance(amount, xp=xp)
    qnet, qgross, qbound, qscale, qresolved = _balance(charge, xp=xp)
    tm, te, tn = chemical._product_parts(
        (BALANCE_RELATIVE_TOLERANCE, gross, xp.abs(z), faraday), shift=scale, xp=xp
    )
    common = xp.maximum(qscale, te)
    qvalue = xp.ldexp(xp.abs(qnet) + qbound, qscale - common)
    tolerance = xp.ldexp(tm, te - common)
    comparison_resolved = ((qvalue != 0) | ((qnet == 0) & (qbound == 0))) & ((tolerance != 0) | ~tn)
    strict = (
        representable
        & resolved
        & qresolved
        & comparison_resolved
        & xp.isfinite(net)
        & xp.isfinite(gross)
        & xp.isfinite(qnet)
        & xp.isfinite(qgross)
        & (xp.abs(net) + bound <= BALANCE_RELATIVE_TOLERANCE * gross)
        & (qvalue <= tolerance)
    )
    nc = ci.size
    padded = xp.concatenate(
        (
            ordered_scatter(charge[:nc], xp.zeros_like(p.initial_cell_charge_C), (ci,), xp=xp),
            ordered_scatter(charge[nc:], xp.zeros_like(p.initial_outside_charge_C), (oi,), xp=xp),
        )
    )
    return ChargeProjection(
        amount,
        charge,
        padded,
        net,
        gross,
        scale,
        qnet,
        qscale,
        tolerance,
        common,
        representable & resolved & qresolved & comparison_resolved,
        strict,
    )


def evaluate(
    charge_reference,
    before_protein,
    after_protein,
    before_endpoint,
    after_endpoint,
    geometry,
    *,
    valence,
    faraday_C_mol,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K,
    implementation,
    xp=jnp,
):
    """Signed conditional endpoint requirement, positive clamp work into system.

    All complete protein buffers use the same component-owner axes. Volumes
    and incidence must exactly match the actual padded field frame, including
    finite reservoir protein stocks. F/R/T must match Cells and the held model.
    Strict material and charge closure apply to all three projections. A
    conservative precision refusal retains all raw chemical/electrical terms.
    This neither publishes state nor supplies a heat, drive or holding law.
    """
    if (
        type(before_endpoint) is not endpoints.ArrayEndpoint
        or type(after_endpoint) is not endpoints.ArrayEndpoint
    ):
        raise ValueError("Require actual paired ArrayEndpoint provider records")
    p = before_endpoint.runtime_layout
    checks = {}
    ci, oi = _geometry(geometry, p, checks, xp=xp)
    sizes = (ci.size, geometry.membrane_to_tissue.size, oi.size)
    for protein in (charge_reference, before_protein, after_protein):
        if type(protein) is not ProteinState:
            raise ValueError("Require three complete ProteinState records")
        for value, size in zip(protein, sizes, strict=True):
            if value.shape != (size,) or value.dtype != xp.float64:
                raise ValueError("Require original float64 protein axes matching WorkGeometry")
    checks["protein/domain"] = xp.all(
        xp.stack(
            [
                xp.all(xp.isfinite(value) & (value >= 0))
                for protein in (charge_reference, before_protein, after_protein)
                for value in protein
            ]
        )
    )
    frame = tuple(
        xp.asarray(v)
        for v in (
            valence,
            faraday_C_mol,
            temperature_K,
            standard_concentration_mol_m3,
            gas_constant_J_mol_K,
        )
    )
    if any(v.shape != () or v.dtype != xp.float64 for v in frame):
        raise ValueError("Require explicit scalar float64 z, F, T, c0 and R")
    z, faraday, t, c0, gas = frame
    checks["frame/Cells_SI_parameters"] = (
        xp.isfinite(z) & (faraday == F) & (gas == R) & (t == p.temperature)
    )
    volume = xp.concatenate((geometry.cell_volume_m3, geometry.environment_volume_m3))
    stocks = [
        xp.concatenate((s.cell_mol_m3, s.environment_mol_m3))
        for s in (charge_reference, before_protein, after_protein)
    ]
    checks["projection/absolute_stocks_representable"] = xp.all(
        xp.stack([_quantities(stock, volume, z, faraday, xp=xp)[2] for stock in stocks])
    )
    projections = [
        _projection(a, b, volume, ci, oi, p, z, faraday, xp=xp)
        for a, b in ((stocks[0], stocks[1]), (stocks[0], stocks[2]), (stocks[1], stocks[2]))
    ]
    bp, ep, request = projections
    for label, point in zip(("before", "after", "requested"), projections, strict=True):
        checks["projection/" + label + "_representable"] = point.representable
        checks["projection/" + label + "_strict_material_charge"] = point.strict_valid
    for label, source, expected in (
        ("before", before_endpoint, bp.padded_charge_delta_C),
        ("after", after_endpoint, ep.padded_charge_delta_C),
    ):
        if (
            source.protein_charge_increment_C.shape != expected.shape
            or source.protein_charge_increment_C.dtype != xp.float64
        ):
            raise ValueError("Require the original padded float64 source charge axes")
        checks["association/" + label + "_protein_charge"] = xp.all(
            source.protein_charge_increment_C == expected
        )
    chem = chemical.change(
        before_protein,
        after_protein,
        geometry.cell_volume_m3,
        geometry.environment_volume_m3,
        temperature_K=t,
        standard_concentration_mol_m3=c0,
        gas_constant_J_mol_K=gas,
        xp=xp,
    )
    elec = electrical.evaluate(
        before_endpoint,
        after_endpoint,
        request.padded_charge_delta_C,
        implementation=implementation,
        xp=xp,
    )
    checks["chemical/strict_closed"] = chem.closed_valid
    checks["electrical/complete_endpoint_checks"] = elec.valid
    lost_request = (request.padded_charge_delta_C != 0) & (
        elec.represented_material_charge_change_C == 0
    )
    checks["precision/requested_charge_response"] = ~xp.any(lost_request)
    terms = xp.stack(
        (chem.total_free_energy_change_pJ, elec.capacitor_energy_change_pJ, -elec.clamp_work_pJ)
    )
    high, low = chemical._sum_pair(terms, xp=xp)
    work = high + low
    addition_bound = 64 * EPS * _sum(xp.abs(terms), xp=xp)
    unchanged_field = xp.all(before_endpoint.potential_V == after_endpoint.potential_V)
    unchanged_charge = xp.all(request.padded_charge_delta_C == 0)
    electric_bound = xp.where(
        unchanged_field & unchanged_charge, 0.0, elec.arithmetic_work_bound_pJ
    )
    component_bound = chem.roundoff_bound_pJ + electric_bound
    work_bound = addition_bound + component_bound
    unchanged_stocks = xp.all(stocks[1] == stocks[2])
    checks["precision/conditional_work"] = (unchanged_stocks & unchanged_field) | (
        xp.abs(work) > work_bound
    )
    checks["work/finite"] = xp.all(
        xp.isfinite(xp.stack((work, low, addition_bound, component_bound, work_bound)))
    )
    checks = {key: checks[key] for key in sorted(checks)}
    return ConditionalProteinWork(
        xp.all(xp.stack(tuple(checks.values()))),
        work,
        low,
        addition_bound,
        component_bound,
        work_bound,
        chem,
        elec,
        bp,
        ep,
        request,
        checks,
        dict(
            lost_requested_charge_mask=lost_request,
            unchanged_stocks=unchanged_stocks,
            unchanged_field=unchanged_field,
            electrical_arithmetic_bound_used_pJ=electric_bound,
            work_input_terms_pJ=terms,
            temperature_K=t,
            standard_concentration_mol_m3=c0,
            gas_constant_J_mol_K=gas,
            valence=z,
            faraday_C_mol=faraday,
        ),
    )
