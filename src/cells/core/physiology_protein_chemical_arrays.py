"""Array ideal-protein chemical endpoint diagnostics in an explicit SI frame.

This optional Cells ideal functional is not a heat or physical driving law.
Geometry/owner provenance, host admission and any work protocol stay outside
this port. No Decimal, host transfer, random draw or mutable state is used.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.physiology_perturbation_step import BALANCE_RELATIVE_TOLERANCE
from cells.numerics.physiology_protein_interval_arrays import _log_ratio, _two_product, _two_sum
from cells.processes.betse_perturbations import ProteinState

EPS = 2.220446049250313e-16


class MaterialBalance(NamedTuple):
    net_mol: object
    gross_mol: object
    tolerance_mol: object
    display_representable: object
    net_normalized: object
    net_remainder_normalized: object
    gross_normalized: object
    roundoff_bound_normalized: object
    tolerance_normalized: object
    binary_exponent: object
    strict_valid: object


class OwnerChange(NamedTuple):
    value_pJ: object
    local_parts_pJ: object
    rounding_bound_pJ: object
    valid: object
    before_chemical_potential_J_mol: object
    after_chemical_potential_J_mol: object
    before_zero: object
    after_zero: object
    underflow: object
    overflow: object
    ambiguous: object
    potential_representable: object


class ProteinChemicalChange(NamedTuple):
    valid: object
    strict_conservation_valid: object
    closed_valid: object
    cell_free_energy_change_pJ: object
    environment_free_energy_change_pJ: object
    total_free_energy_change_pJ: object
    cell_before_chemical_potential_J_mol: object
    cell_after_chemical_potential_J_mol: object
    environment_before_chemical_potential_J_mol: object
    environment_after_chemical_potential_J_mol: object
    material: MaterialBalance
    roundoff_bound_pJ: object
    diagnostics: object


def _product_parts(factors, divisors=(), *, shift=0, xp):
    arrays = xp.broadcast_arrays(*(xp.asarray(v, dtype=xp.float64) for v in (*factors, *divisors)))
    value = xp.ones_like(arrays[0])
    exponent = xp.zeros_like(value, dtype=xp.int32) + shift
    nonzero = xp.ones_like(value, dtype=bool)
    for i, factor in enumerate(arrays):
        m, e = xp.frexp(factor)
        if i < len(factors):
            value *= m
            exponent += e
            nonzero &= factor != 0
        else:
            value /= m
            exponent -= e
    return value, exponent, nonzero


def _product(factors, divisors=(), *, shift=0, xp):
    value, exponent, nonzero = _product_parts(factors, divisors, shift=shift, xp=xp)
    result = xp.ldexp(value, exponent)
    return result, nonzero & (result == 0), ~xp.isfinite(result)


def _bound(estimate, nonzero, *, xp):
    # Only the error bound rounds outward: no stock/energy is changed. Keeping
    # a normal bound avoids backend flush of subnormal uncertainty estimates.
    tiny = xp.finfo(xp.float64).tiny
    return xp.where(nonzero & (estimate < tiny), tiny, estimate * (1 + 8 * EPS))


def _subnormal(value, *, xp):
    bits = value.view(np.uint64) if xp is np else jax.lax.bitcast_convert_type(value, xp.uint64)
    return ((bits & xp.uint64(0x7FF0000000000000)) == 0) & (
        (bits & xp.uint64(0xFFFFFFFFFFFFF)) != 0
    )


def _sum_pair(values, *, xp):
    if not values.size:
        return xp.asarray(0.0), xp.asarray(0.0)

    def step(i, carry):
        total, remainder = carry
        result, error = _two_sum(total, values[i], xp=xp)
        return result, remainder + error

    start = (xp.asarray(0.0), xp.asarray(0.0))
    if xp is np:
        for i in range(values.size):
            start = step(i, start)
        return _two_sum(*start, xp=xp)
    return _two_sum(*jax.lax.fori_loop(0, values.size, step, start), xp=xp)


def _material(before, after, volume, domain, *, xp):
    dh, dl = _two_sum(after, -before, xp=xp)
    mv, ev = xp.frexp(volume)
    parts, exponents = [], []
    for delta in (dh, dl):
        md, ed = xp.frexp(delta)
        high, low = _two_product(mv, md, xp=xp)
        parts.extend((high, low))
        exponents.extend((ev + ed, ev + ed))
    values = xp.concatenate(parts)
    powers = xp.concatenate(exponents)
    scale = xp.max(xp.where(values != 0, powers, -8192), initial=-8192)
    scale = xp.where(xp.any(values != 0), scale, 0)
    normalized = xp.ldexp(values, powers - scale)
    high, low = _sum_pair(normalized, xp=xp)
    # Gross belongs to each physical owner's signed change, not to the sum of
    # absolute product remainders. Normalized owner signs agree with dC.
    n = before.size
    owner_values = sum(normalized[i * n : (i + 1) * n] for i in range(4))
    gross = xp.sum(xp.abs(owner_values))
    rounding = 64 * EPS * xp.sum(xp.abs(normalized))
    tolerance = BALANCE_RELATIVE_TOLERANCE * gross
    net = high + low
    strict = domain & xp.isfinite(net) & xp.isfinite(gross) & (xp.abs(net) + rounding <= tolerance)
    displayed = (xp.ldexp(net, scale), xp.ldexp(gross, scale), xp.ldexp(tolerance, scale))
    originals = (net, gross, tolerance)
    representable = xp.all(
        xp.stack(
            [
                xp.isfinite(v) & ((v != 0) | (a == 0))
                for v, a in zip(displayed, originals, strict=True)
            ]
        )
    )
    return MaterialBalance(
        *displayed, representable, high, low, gross, rounding, tolerance, scale, strict
    )


def _owner(before, after, volume, pivot, t, c0, r, *, xp):
    domain = (
        xp.isfinite(before)
        & xp.isfinite(after)
        & xp.isfinite(volume)
        & (before >= 0)
        & (after >= 0)
        & (volume > 0)
    )
    normal = ~(_subnormal(before, xp=xp) | _subnormal(after, xp=xp) | _subnormal(volume, xp=xp))
    live = domain & normal
    b, e, v = (
        xp.where(live, value, neutral)
        for value, neutral in ((before, 0.0), (after, 0.0), (volume, 1.0))
    )
    bp, ep = b > 0, e > 0
    bb, ee = xp.where(bp, b, 1.0), xp.where(ep, e, 1.0)
    logb = _log_ratio(bb, xp.zeros_like(bb), pivot, 1.0, xp=xp)
    loge = _log_ratio(ee, xp.zeros_like(ee), pivot, 1.0, xp=xp)
    common = _log_ratio(pivot, xp.asarray(0.0), c0, 1.0, xp=xp)
    dh, dl = _two_sum(e, -b, xp=xp)
    thermal = (1e12, r, t, v)
    linear = [_product((*thermal, d, logb), xp=xp) for d in (dh, dl)]
    ratio = dh / bb
    small = bp & ep & xp.isfinite(ratio) & (xp.abs(ratio) <= 0.0625)
    rr = xp.where(small, ratio, 0.0)
    coefficient = xp.zeros_like(rr)
    for k in range(22, 1, -1):
        coefficient = coefficient * rr + (-1.0) ** k / (k * (k - 1))
    quadratic = _product((*thermal, dh, dh, coefficient), (bb,), xp=xp)
    logstep = _log_ratio(ee, xp.zeros_like(ee), bb, 1.0, xp=xp)
    regular = [
        _product((*thermal, e, logstep), xp=xp),
        _product((*thermal, -dh), xp=xp),
        _product((*thermal, -dl), xp=xp),
    ]
    positive_parts = [
        linear[0],
        linear[1],
        tuple(
            xp.where(small, quadratic[i], sum(a[i] for a in regular))
            if i == 0
            else xp.where(small, quadratic[i], xp.any(xp.stack([a[i] for a in regular]), axis=0))
            for i in range(3)
        ),
    ]
    start = _product((*thermal, -b, logb - 1), xp=xp)
    end = _product((*thermal, e, loge - 1), xp=xp)
    zero_branch = tuple(start[i] + end[i] if i == 0 else start[i] | end[i] for i in range(3))
    both = bp & ep
    local_parts = xp.stack(
        [
            xp.where(both, a[0], zero_branch[0] if i == 0 else 0.0)
            for i, a in enumerate(positive_parts)
        ]
    )
    common_parts = [_product((*thermal, d, common), xp=xp) for d in (dh, dl)]
    local = xp.sum(local_parts, axis=0)
    value = local + sum(a[0] for a in common_parts)
    underflow = xp.where(
        both, xp.any(xp.stack([a[1] for a in positive_parts]), axis=0), zero_branch[1]
    )
    overflow = xp.where(
        both, xp.any(xp.stack([a[2] for a in positive_parts]), axis=0), zero_branch[2]
    )
    underflow |= xp.any(xp.stack([a[1] for a in common_parts]), axis=0)
    overflow |= xp.any(xp.stack([a[2] for a in common_parts]), axis=0) | ~xp.isfinite(value)
    gross = xp.sum(xp.abs(local_parts), axis=0) + sum(xp.abs(a[0]) for a in common_parts)
    log_error = _product(
        (*thermal, xp.abs(dh) + xp.abs(dl), 64 * EPS * (xp.abs(logb) + xp.abs(common))), xp=xp
    )[0]
    bound = _bound(128 * EPS * gross + log_error, b != e, xp=xp)
    changed = b != e
    ambiguous = changed & (xp.abs(value) <= bound)
    potentials = []
    mu_valid = xp.ones_like(bp)
    for c, positive in ((bb, bp), (ee, ep)):
        log = _log_ratio(c, xp.zeros_like(c), c0, 1.0, xp=xp)
        potential, lost, over = _product((r, t, log), xp=xp)
        potentials.append(xp.where(positive, potential, -xp.inf))
        mu_valid &= ~positive | (~lost & ~over)
    valid = live & mu_valid & ~overflow & xp.isfinite(bound) & ~ambiguous
    valid &= ~(changed & underflow & (value == 0))
    return OwnerChange(
        value,
        local_parts,
        bound,
        valid,
        *potentials,
        before == 0,
        after == 0,
        underflow,
        overflow,
        ambiguous,
        mu_valid,
    )


def change(
    reference_protein,
    current_protein,
    cell_volume_m3,
    environment_volume_m3,
    *,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K,
    xp=jnp,
):
    """Chemical diagnostics; closed_valid additionally requires strict material.

    Owner vectors/volumes share component-owner order. Membrane views are not
    inventory. All frame scalars are explicit; this is not work/heat admission.
    Empty vectors and zero stocks have their continuous ideal limits.
    """
    if type(reference_protein) is not ProteinState or type(current_protein) is not ProteinState:
        raise ValueError("Require complete paired ProteinState arrays")
    for a, b in zip(reference_protein, current_protein, strict=True):
        if a.ndim != 1 or a.shape != b.shape or a.dtype != xp.float64 or b.dtype != xp.float64:
            raise ValueError("Require matching one-dimensional float64 protein buffers")
    volumes = (xp.asarray(cell_volume_m3), xp.asarray(environment_volume_m3))
    before = (reference_protein.cell_mol_m3, reference_protein.environment_mol_m3)
    after = (current_protein.cell_mol_m3, current_protein.environment_mol_m3)
    if any(
        v.shape != a.shape or v.dtype != xp.float64 for v, a in zip(volumes, before, strict=True)
    ):
        raise ValueError("Require float64 m3 volumes on the matching owner axes")
    frame = tuple(
        xp.asarray(v) for v in (temperature_K, standard_concentration_mol_m3, gas_constant_J_mol_K)
    )
    if any(v.shape != () or v.dtype != xp.float64 for v in frame):
        raise ValueError("Require explicit scalar float64 T, c0 and R")
    frame_valid = xp.all(
        xp.stack([xp.isfinite(v) & (v > 0) & ~_subnormal(v, xp=xp) for v in frame])
    )
    t, c0, r = (xp.where(frame_valid, value, 1.0) for value in frame)
    maximum = xp.max(xp.concatenate((*before, *after)), initial=0.0)
    pivot = xp.where(xp.isfinite(maximum) & (maximum > 0), maximum, c0)
    owners = [
        _owner(b, e, v, pivot, t, c0, r, xp=xp)
        for b, e, v in zip(before, after, volumes, strict=True)
    ]
    membrane_valid = xp.all(
        xp.stack(
            [
                xp.all(xp.isfinite(s.membrane_mol_m3) & (s.membrane_mol_m3 >= 0))
                for s in (reference_protein, current_protein)
            ]
        )
    )
    b, e, v = (xp.concatenate(a) for a in (before, after, volumes))
    domain = (
        xp.all(xp.isfinite(b) & xp.isfinite(e) & xp.isfinite(v) & (b >= 0) & (e >= 0) & (v > 0))
        & membrane_valid
    )
    normal = ~xp.any(_subnormal(b, xp=xp) | _subnormal(e, xp=xp) | _subnormal(v, xp=xp))
    material = _material(b, e, v, domain & normal, xp=xp)
    common = _log_ratio(pivot, xp.asarray(0.0), c0, 1.0, xp=xp)
    common_parts = [
        _product_parts((1e12, r, t, common, n), shift=material.binary_exponent, xp=xp)
        for n in (material.net_normalized, material.net_remainder_normalized)
    ]
    local_parts = xp.concatenate([o.local_parts_pJ.reshape(-1) for o in owners])
    local_m, local_e = xp.frexp(local_parts)
    energy_m = xp.concatenate((local_m, xp.stack([p[0] for p in common_parts])))
    energy_e = xp.concatenate((local_e, xp.stack([p[1] for p in common_parts])))
    energy_scale = xp.max(xp.where(energy_m != 0, energy_e, -8192), initial=-8192)
    energy_scale = xp.where(xp.any(energy_m != 0), energy_scale, 0)
    total_hi, total_lo = _sum_pair(xp.ldexp(energy_m, energy_e - energy_scale), xp=xp)
    total_normalized = total_hi + total_lo
    total = xp.ldexp(total_normalized, energy_scale)
    material_uncertainty = xp.abs(
        _product(
            (1e12, r, t, common, material.roundoff_bound_normalized),
            shift=material.binary_exponent,
            xp=xp,
        )[0]
    )
    material_uncertainty = _bound(
        material_uncertainty, (material.roundoff_bound_normalized != 0) & (common != 0), xp=xp
    )
    common_display = [xp.ldexp(p[0], p[1]) for p in common_parts]
    estimate = (
        sum(xp.sum(o.rounding_bound_pJ) for o in owners)
        + material_uncertainty
        + 64 * EPS * (xp.sum(xp.abs(local_parts)) + sum(xp.abs(p) for p in common_display))
    )
    unchanged = xp.all(b == e)
    bound = _bound(estimate, ~unchanged, xp=xp)
    total_ambiguous = ~unchanged & (xp.abs(total) <= bound)
    valid = (
        frame_valid
        & domain
        & normal
        & xp.all(xp.stack([xp.all(o.valid) for o in owners]))
        & xp.isfinite(total)
        & xp.isfinite(bound)
        & ~total_ambiguous
        & ~((total_normalized != 0) & (total == 0))
        & xp.all(
            xp.isfinite(xp.stack((material.net_mol, material.gross_mol, material.tolerance_mol)))
        )
    )
    diagnostics = dict(
        frame_valid=frame_valid,
        owner_domain_valid=domain,
        normal_inputs=normal,
        concentration_pivot_mol_m3=pivot,
        unchanged=unchanged,
        total_cancellation_ambiguous=total_ambiguous,
        total_energy_normalized=total_normalized,
        total_energy_binary_exponent=energy_scale,
        cell_before_zero=owners[0].before_zero,
        cell_after_zero=owners[0].after_zero,
        environment_before_zero=owners[1].before_zero,
        environment_after_zero=owners[1].after_zero,
        cell_underflow=owners[0].underflow,
        environment_underflow=owners[1].underflow,
        cell_overflow=owners[0].overflow,
        environment_overflow=owners[1].overflow,
        cell_ambiguous=owners[0].ambiguous,
        environment_ambiguous=owners[1].ambiguous,
        cell_potential_representable=owners[0].potential_representable,
        environment_potential_representable=owners[1].potential_representable,
        temperature_K=frame[0],
        standard_concentration_mol_m3=frame[1],
        gas_constant_J_mol_K=frame[2],
    )
    return ProteinChemicalChange(
        valid,
        material.strict_valid,
        valid & material.strict_valid,
        owners[0].value_pJ,
        owners[1].value_pJ,
        total,
        owners[0].before_chemical_potential_J_mol,
        owners[0].after_chemical_potential_J_mol,
        owners[1].before_chemical_potential_J_mol,
        owners[1].after_chemical_potential_J_mol,
        material,
        bound,
        diagnostics,
    )
