"""Pure array held-protein interval balances for four static ordinary families.

The caller admits source/geometry/charge provenance and original anchors. This
port owns neither publication nor high-precision host admission. Returned
precision flags conservatively refuse unresolved arithmetic without widening
any physical balance tolerance. No Decimal or host array transfer occurs here.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.models import compartment_reactions as chemistry
from cells.models import physiology_permeability_view as view
from cells.models import physiology_protein_charge_rhs as charged
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy as fuel
from cells.models import surface_kinetic as kinetic
from cells.models import surface_tissue as passive
from cells.numerics import surface_field as field
from cells.numerics.extracellular_field import ordered_scatter
from cells.processes.electrochemistry import CHARGE_PER_FMOL, F, R

EPS = 2.220446049250313e-16
MIN_SUBNORMAL = 5e-324


class IdealIncrement(NamedTuple):
    value_pJ: object
    rounding_bound_pJ: object
    valid: object
    domain_valid: object
    underflow: object
    overflow: object
    cancellation_ambiguous: object


class ArrayIntervalAccounting(NamedTuple):
    valid: object
    balances: object
    limits: object
    checks: object
    energy_terms: object
    diagnostics: object
    first_invalid_check: object


class ArrayEndpoint(NamedTuple):
    source_state: object
    source_control: object
    runtime_layout: object
    protein_charge_increment_C: object
    membrane_voltage_V: object
    potential_V: object
    charged_rates_valid: object
    domain_valid: object
    charge_grouping_roundoff_C: object


def _barrier(value, *, xp):
    return value if xp is np else jax.lax.optimization_barrier(value)


def _two_sum(a, b, *, xp):
    total = _barrier(a + b, xp=xp)
    back = _barrier(total - a, xp=xp)
    error = _barrier((a - _barrier(total - back, xp=xp)) + (b - back), xp=xp)
    return total, error


def _two_product(a, b, *, xp):
    # Only frexp mantissas enter: splitting cannot overflow or underflow.
    product = _barrier(a * b, xp=xp)

    def split(value):
        large = _barrier(134217729.0 * value, xp=xp)
        high = _barrier(large - _barrier(large - value, xp=xp), xp=xp)
        return high, value - high

    ah, al = split(a)
    bh, bl = split(b)
    error = _barrier(_barrier(ah * bh, xp=xp) - product, xp=xp)
    for term in (_barrier(ah * bl, xp=xp), _barrier(al * bh, xp=xp), _barrier(al * bl, xp=xp)):
        error = _barrier(error + term, xp=xp)
    return product, error


def _scaled_product(numerators, denominators=(), *, xp):
    """Multiply/divide mantissas, applying the combined binary exponent once."""
    arrays = xp.broadcast_arrays(
        *(xp.asarray(v, dtype=xp.float64) for v in (*numerators, *denominators))
    )
    value = xp.ones_like(arrays[0])
    exponent = xp.zeros_like(value, dtype=xp.int32)
    nonzero = xp.ones_like(value, dtype=bool)
    for i, factor in enumerate(arrays):
        mantissa, power = xp.frexp(factor)
        if i < len(numerators):
            value = value * mantissa
            exponent = exponent + power
            nonzero &= factor != 0
        else:
            value = value / mantissa
            exponent = exponent - power
    result = xp.ldexp(value, exponent)
    underflow = nonzero & (result == 0)
    overflow = ~xp.isfinite(result)
    return result, underflow, overflow


def _log_ratio(high, low, volume, standard, *, xp):
    """log((high+low)/(volume*standard)), retaining near-equilibrium stock bits."""
    mh, eh = xp.frexp(high)
    mv, ev = xp.frexp(volume)
    mc, ec = xp.frexp(standard)
    product, product_low = _two_product(mv, mc, xp=xp)
    exponent = eh - ev - ec
    nearby = xp.abs(exponent) <= 2
    nh = xp.ldexp(mh, xp.where(nearby, exponent, 0))
    ml, el = xp.frexp(low)
    nl = xp.ldexp(ml, xp.where(nearby, el - ev - ec, 0))
    difference, error = _two_sum(nh, -product, xp=xp)
    dh, dl = _two_sum(difference, error - product_low, xp=xp)
    relative = (dh + (dl + nl)) / product
    close = nearby & (xp.abs(relative) <= 0.125)
    # Neutral branch arguments protect evaluation; physical inputs are retained
    # by the caller and the primitive's separate domain predicate.
    near = xp.log1p(xp.where(close, relative, 0.0))
    regular = xp.log(mh) - xp.log(mv) - xp.log(mc) + exponent * xp.log(2.0) + xp.log1p(low / high)
    return xp.where(close, near, regular)


def ideal_change(
    anchor,
    before_increment,
    after_increment,
    volume,
    standard,
    mu0_rt,
    temperature,
    active,
    *,
    xp=jnp,
):
    """Stable per-species/owner ideal DeltaG and explicit array arithmetic flags.

    Chemical stocks remain the original anchor plus the separate increments.
    A small-r polynomial computes h(r)/r**2; scaled dN*dN/N preserves quadratic
    energy when forming r*r first would underflow. Domain-neutral operands are
    used only during evaluation of rejected entries, never as repaired stocks.
    """
    a, b, e, v, c, mu, live = xp.broadcast_arrays(
        anchor, before_increment, after_increment, volume, standard, mu0_rt, active
    )
    nh, nl = _two_sum(a, b, xp=xp)
    endh, endl = _two_sum(a, e, xp=xp)
    dh, dl = _two_sum(e, -b, xp=xp)
    domain = (
        xp.isfinite(a)
        & xp.isfinite(b)
        & xp.isfinite(e)
        & xp.isfinite(v)
        & xp.isfinite(c)
        & xp.isfinite(mu)
        & xp.isfinite(nh)
        & xp.isfinite(endh)
        & (a > 0)
        & (nh > 0)
        & (endh > 0)
        & (v > 0)
        & (c > 0)
        & xp.isfinite(temperature)
        & (temperature > 0)
    )
    take = live & domain
    nn, nnl, ee, eel, vv, cc, mm, dd, ddl = (
        xp.where(take, value, neutral)
        for value, neutral in (
            (nh, 1.0),
            (nl, 0.0),
            (endh, 1.0),
            (endl, 0.0),
            (v, 1.0),
            (c, 1.0),
            (mu, 0.0),
            (dh, 0.0),
            (dl, 0.0),
        )
    )
    log = _log_ratio(nn, nnl, vv, cc, xp=xp)
    mh, ml = _two_sum(mm, log, xp=xp)
    thermal = (0.001, R, temperature)
    linear_parts = [
        _scaled_product((*thermal, change, potential), xp=xp)
        for change in (dd, ddl)
        for potential in (mh, ml)
    ]
    ratio = dd / nn
    small = xp.isfinite(ratio) & (xp.abs(ratio) <= 0.0625)
    r = xp.where(small, ratio, 0.0)
    coefficient = xp.zeros_like(r)
    for k in range(22, 1, -1):
        coefficient = coefficient * r + (-1.0) ** k / (k * (k - 1))
    quadratic_small = _scaled_product((*thermal, dd, dd, coefficient), (nn,), xp=xp)
    log_increment = _log_ratio(ee, eel, nn, xp.ones_like(nn), xp=xp) - xp.log1p(nnl / nn)
    large_parts = [
        _scaled_product((*thermal, ee, log_increment), xp=xp),
        _scaled_product((*thermal, eel, log_increment), xp=xp),
        _scaled_product((*thermal, -dd), xp=xp),
        _scaled_product((*thermal, -ddl), xp=xp),
    ]
    linear = sum(part[0] for part in linear_parts)
    quadratic_large = sum(part[0] for part in large_parts)
    quadratic = xp.where(small, quadratic_small[0], quadratic_large)
    raw = linear + quadratic
    changed = (dd != 0) | (ddl != 0)
    underflow = xp.any(xp.stack([part[1] for part in linear_parts]), axis=0) | xp.where(
        small, quadratic_small[1], xp.any(xp.stack([part[1] for part in large_parts]), axis=0)
    )
    overflow = (
        xp.any(xp.stack([part[2] for part in linear_parts]), axis=0)
        | xp.where(
            small, quadratic_small[2], xp.any(xp.stack([part[2] for part in large_parts]), axis=0)
        )
        | ~xp.isfinite(raw)
        | (xp.isfinite(a) & xp.isfinite(b) & ~xp.isfinite(nh))
        | (xp.isfinite(a) & xp.isfinite(e) & ~xp.isfinite(endh))
    )
    gross = sum(xp.abs(part[0]) for part in linear_parts) + xp.where(
        small, xp.abs(quadratic_small[0]), sum(xp.abs(part[0]) for part in large_parts)
    )
    ambiguous = changed & (raw == 0) & (gross > 0)
    log_budget = _scaled_product(
        (*thermal, xp.abs(dd) + xp.abs(ddl), xp.abs(mm) + xp.abs(log) + 1.0), xp=xp
    )[0]
    bound = 256 * EPS * (gross + log_budget) + xp.where(underflow, MIN_SUBNORMAL, 0.0)
    valid = (
        domain & ~overflow & xp.isfinite(bound) & ~(underflow & (raw == 0) & changed) & ~ambiguous
    )
    return IdealIncrement(
        xp.where(live, raw, 0.0),
        xp.where(live, bound, 0.0),
        xp.where(live, valid, True),
        xp.where(live, domain, True),
        live & underflow,
        live & overflow,
        live & ambiguous,
    )


def _ideal_groups(before, after, p, *, has_store, has_fuel, xp):
    """One primitive graph for all chemical owners and three fuel intervals."""
    entries = [
        (
            p.extracellular_amount_reference,
            before.extracellular_amount_increment,
            after.extracellular_amount_increment,
            p.extracellular_volume,
            1.0,
            0.0,
            p.temperature,
            p.outside_active,
        )
    ]
    if has_store:
        for i in range(p.er_initial_amount.shape[0]):
            b, e, c = (
                calcium.store_state(before, i),
                calcium.store_state(after, i),
                calcium.store_layout(p, i),
            )
            entries.append(
                (
                    c.initial_amount,
                    b.amount_increment,
                    e.amount_increment,
                    c.volume,
                    c.standard_concentration,
                    c.standard_mu_RT[:, None],
                    c.temperature,
                    c.active,
                )
            )
    else:
        entries.append(
            (
                p.amount_reference,
                before.amount_increment,
                after.amount_increment,
                p.volume,
                1.0,
                0.0,
                p.temperature,
                p.active,
            )
        )
    count = len(entries)
    if has_fuel:
        zero = xp.zeros_like(before.energy_amount_increment_fmol)
        for b, e in (
            (zero, before.energy_amount_increment_fmol),
            (zero, after.energy_amount_increment_fmol),
            (before.energy_amount_increment_fmol, after.energy_amount_increment_fmol),
        ):
            entries.append(
                (
                    p.energy_initial_amount_fmol,
                    b,
                    e,
                    p.volume,
                    fuel.energy.STANDARD_STATE_mM,
                    0.0,
                    p.temperature,
                    p.active,
                )
            )
    groups = [xp.broadcast_arrays(*entry) for entry in entries]
    joined = [xp.concatenate([entry[i].reshape(-1) for entry in groups]) for i in range(8)]
    combined = ideal_change(*joined, xp=xp)
    results, start = [], 0
    for group in groups:
        size, shape = group[0].size, group[0].shape
        results.append(
            IdealIncrement(*(value[start : start + size].reshape(shape) for value in combined))
        )
        start += size
    return results[:count], results[count:]


def _pool_change(before, after, p, mixing, *, xp):
    dh, dl = _two_sum(
        after.energy_amount_increment_fmol[0], -before.energy_amount_increment_fmol[0], xp=xp
    )
    standard_parts = [
        _scaled_product((-0.001, p.energy_delta_g0_J_mol, d), xp=xp) for d in (dh, dl)
    ]
    standard = sum(value[0] for value in standard_parts)
    free = xp.sum(mixing.value_pJ, axis=0) + standard
    bound = xp.sum(mixing.rounding_bound_pJ, axis=0) + 32 * EPS * (
        xp.sum(xp.abs(mixing.value_pJ), axis=0) + sum(xp.abs(value[0]) for value in standard_parts)
    )
    underflow = xp.any(mixing.underflow, axis=0) | xp.any(
        xp.stack([v[1] for v in standard_parts]), axis=0
    )
    overflow = xp.any(mixing.overflow, axis=0) | xp.any(
        xp.stack([v[2] for v in standard_parts]), axis=0
    )
    valid = xp.all(mixing.valid) & xp.all(xp.isfinite(free)) & ~xp.any(overflow)
    valid &= ~xp.any(
        underflow
        & (free == 0)
        & xp.any(after.energy_amount_increment_fmol != before.energy_amount_increment_fmol, axis=0)
    )
    return free, bound, valid, underflow, overflow


def _pool_balance(before, after, p, free, *, xp):
    works = []
    for state in (before, after):
        works.append(
            xp.concatenate(
                (
                    state.metabolic_work_pJ,
                    state.plasma_metabolic_work_pJ,
                    state.er_metabolic_work_pJ,
                )
            )
        )
    transferred = ordered_scatter(
        works[1] - works[0], xp.zeros_like(p.volume), (fuel.pump_routes(p, xp=xp).owner,), xp=xp
    )
    port = ordered_scatter(
        (
            (after.regeneration_dissipated_energy_pJ - before.regeneration_dissipated_energy_pJ)
            - (after.regeneration_supplied_work_pJ - before.regeneration_supplied_work_pJ)
        ),
        xp.zeros_like(p.volume),
        (p.regeneration_owner,),
        xp=xp,
    )
    value = free + transferred + port
    bound = 64 * EPS * (xp.abs(free) + xp.abs(transferred) + xp.abs(port))
    return value, bound


def _balances(state, p, *, has_store, has_fuel, xp):
    hm = state.membrane_transferred
    if hasattr(state, "channel_transferred"):
        hm = hm + kinetic.channel_to_membrane(state.channel_transferred, p, xp=xp)
        hm = hm - p.stoichiometry * state.pump_cycles
    if has_store:
        hm = hm + p.plasma_ca_selector * (
            state.plasma_pump_cycles
            + state.plasma_exchange_cycles
            + state.calcium_channel_transferred
        )
        hm = hm - 3 * p.plasma_na_selector * state.plasma_exchange_cycles
    di, do = state.amount_increment, state.extracellular_amount_increment
    scatter = ordered_scatter
    local = (
        di
        + scatter(hm, di, (p.membrane_cell,), xp=xp)
        + scatter(state.junction_transferred, di, (p.junction_sender,), xp=xp)
        - scatter(state.junction_transferred, di, (p.junction_receiver,), xp=xp)
    )
    outside = (
        do
        - scatter(hm, do, (p.membrane_outside,), xp=xp)
        + scatter(state.face_transferred, do, (p.face_sender,), xp=xp)
        - scatter(state.face_transferred, do, (p.face_receiver,), xp=xp)
        - state.reservoir_supplied
    )
    q, cap, _ = passive.capacitor_change(state, p, xp=xp)
    n = p.active.size
    original_q = xp.concatenate((p.initial_cell_charge_C, p.initial_outside_charge_C))
    original_phi = field._capacitor_solve(
        original_q,
        xp.concatenate((xp.zeros_like(p.initial_cell_charge_C), p.boundary_V)),
        passive.field_layout(p),
        xp=xp,
    )
    required = p.field_active & ~xp.concatenate((xp.zeros(n, dtype=bool), p.reservoir))
    charge = xp.where(required, p.field_capacitor_matrix @ original_phi - original_q + cap - q, 0.0)
    co = xp.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1.0)
    mu = R * p.temperature * xp.log(co) + p.valence * F * p.boundary_V
    result = dict(
        local=local,
        outside=outside,
        total=xp.sum(di, axis=1) + xp.sum(do, axis=1) - xp.sum(state.reservoir_supplied, axis=1),
        charge=charge,
        electrode=state.electrode_charge_transferred_C - xp.where(p.reservoir, cap[n:], 0.0),
        global_charge=xp.sum(state.electrode_charge_transferred_C)
        + CHARGE_PER_FMOL * xp.sum(p.valence * state.reservoir_supplied),
        reservoir_work=state.reservoir_work_pJ
        - 0.001 * xp.sum(mu * state.reservoir_supplied, axis=0),
        electrode_work=state.electrode_work_pJ
        - 1e12 * p.boundary_V * state.electrode_charge_transferred_C,
    )
    if hasattr(state, "metabolic_work_pJ") and not has_fuel:
        result["metabolic_work"] = (
            state.metabolic_work_pJ + 0.001 * p.pump_drive * state.pump_cycles
        )
    if has_store:
        residues, er_work = [], []
        for i in range(p.er_initial_amount.shape[0]):
            s, c = calcium.store_state(state, i), calcium.store_layout(p, i)
            transfer = (
                s.passive_transferred
                + (s.pump_transferred + s.release_transferred) * c.calcium_selector
            )
            influx = p.free_ion_selector @ state.amount_increment[:, i]
            residues.append(
                (
                    s.amount_increment
                    - chemistry.reaction_amount(s.reaction_extent, c, xp=xp)
                    - transfer[:, None] * c.incidence
                    - influx[:, None] * p.cytosol_selector[i]
                )
                / xp.maximum(1.0, c.initial_amount)
            )
            if not has_fuel:
                drive = calcium.er.processes.chemical_drive(
                    calcium.er.pump_parameters(c), c.temperature, xp=xp
                )
                er_work.append(
                    state.er_metabolic_work_pJ[i] + 0.001 * drive * s.pump_transferred[0]
                )
        result["chemical_ledger"] = xp.stack(residues)
        result["ownership"] = calcium.ownership_residual(state, p, xp=xp)
        if not has_fuel:
            result["plasma_metabolic_work"] = (
                state.plasma_metabolic_work_pJ
                + 0.001
                * calcium.process.chemical_drive(
                    calcium.plasma.pump_parameters(p), p.temperature, xp=xp
                )
                * state.plasma_pump_cycles
            )
            result["er_metabolic_work"] = xp.stack(er_work)
    if has_fuel:
        material = fuel.energy.material_balances(
            p.energy_initial_amount_fmol,
            fuel.energy_amounts(state, p),
            fuel.pump_cycles(state, xp=xp),
            fuel.pump_routes(p, xp=xp),
            state.regeneration_cycles_fmol,
            fuel.regeneration_routes(p),
            fuel.pool_parameters(p, xp=xp),
            xp=xp,
        )
        result.update(
            pool_material=material.amount_residual_fmol,
            adenylate=material.adenylate_residual_fmol,
            phosphorus=material.phosphorus_residual_fmol,
            regeneration_work=state.regeneration_supplied_work_pJ
            - 0.001 * p.regeneration_supplied_energy_J_mol * state.regeneration_cycles_fmol,
        )
    return result


def _limits(state, p, tolerance, *, xp):
    q = xp.concatenate((p.initial_cell_charge_C, p.initial_outside_charge_C))
    q = q + passive.charge_increment(state, p, xp=xp)
    has_store = hasattr(state, "chemical_amount_increment")
    electrode = field.CHARGE_ATOL_C
    if not has_store:
        electrode = electrode + field.CHARGE_RTOL * xp.abs(state.electrode_charge_transferred_C)
    energy = calcium.ENERGY_ATOL_PJ if has_store else passive.ENERGY_ATOL_PJ
    return dict(
        local=tolerance[:, None],
        outside=tolerance[:, None],
        total=tolerance,
        charge=field.CHARGE_ATOL_C + field.CHARGE_RTOL * xp.abs(q),
        electrode=electrode,
        global_charge=3e-25,
        energy=energy,
        reservoir_work=3e-12,
        electrode_work=3e-12,
        metabolic_work=3e-12,
        plasma_metabolic_work=3e-12,
        er_metabolic_work=3e-12,
        chemical_ledger=chemistry.ROUND_ATOL,
        ownership=chemistry.ROUND_ATOL,
        pool_material=fuel.POOL_MATERIAL_ATOL_FMOL,
        adenylate=fuel.POOL_MATERIAL_ATOL_FMOL,
        phosphorus=fuel.POOL_MATERIAL_ATOL_FMOL,
        pool_energy=fuel.ENERGY_ATOL_PJ,
        regeneration_work=3e-12,
    )


def _endpoint(state, control, p, delta, implementation, *, xp):
    domain = implementation.domain_valid(state, p, p.active, xp=xp)

    def actual():
        rates = charged.array_readouts(
            state, control, p, delta, implementation=implementation, xp=xp
        )
        return (
            rates.field.rates.membrane_voltage_V,
            rates.field.potential_V,
            rates.valid,
            rates.charge_grouping_roundoff_C,
        )

    def invalid():
        return (
            xp.full_like(p.membrane_capacitance, xp.nan),
            xp.full_like(delta, xp.nan),
            xp.asarray(False),
            xp.full_like(delta, xp.nan),
        )

    if xp is np:
        if not domain:
            return (*invalid(), domain)
        try:
            return (*actual(), domain)
        except np.linalg.LinAlgError:
            return (*invalid(), domain)
    values = jax.lax.cond(domain, actual, invalid)
    return (*values, domain)


def endpoint_values(
    state, control, runtime_layout, protein_charge_increment_C, *, implementation, xp=jnp
):
    """Produce actual charged endpoint data for a separate device accounting call.

    Snapshots retain complete array association, not proof of authorship. They
    must be generated by this provider. No host transfer, random draw, clock
    advance or acceptance occurs. NumPy snapshots do not alias caller buffers.
    """
    if implementation not in view.IMPLEMENTATIONS.values():
        raise ValueError("Require a static exact ordinary implementation")
    delta = xp.asarray(protein_charge_increment_C)
    vm, potential, valid, grouping, domain = _endpoint(
        state, control, runtime_layout, delta, implementation, xp=xp
    )
    snapshot = jax.tree.map(
        lambda value: xp.array(value, copy=True), (state, control, runtime_layout, delta)
    )
    return ArrayEndpoint(*snapshot, vm, potential, valid, domain, grouping)


def _association(endpoint, state, control, p, delta, *, xp):
    if type(endpoint) is not ArrayEndpoint:
        raise ValueError("Require actual ArrayEndpoint provider records")
    if (
        type(endpoint.source_state) is not type(state)
        or type(endpoint.source_control) is not type(control)
        or type(endpoint.runtime_layout) is not type(p)
        or endpoint.membrane_voltage_V.shape != p.membrane_capacitance.shape
        or endpoint.potential_V.shape != delta.shape
        or endpoint.membrane_voltage_V.dtype != xp.float64
        or endpoint.potential_V.dtype != xp.float64
    ):
        raise ValueError("Require complete matching endpoint structures and float64 field axes")
    expected = (state, control, p, delta)
    source = (
        endpoint.source_state,
        endpoint.source_control,
        endpoint.runtime_layout,
        endpoint.protein_charge_increment_C,
    )
    aa, bb = jax.tree.leaves(source), jax.tree.leaves(expected)
    if len(aa) != len(bb) or any(
        a.shape != b.shape or a.dtype != b.dtype for a, b in zip(aa, bb, strict=True)
    ):
        raise ValueError("Endpoint source association has different static shapes/dtypes")
    return xp.all(xp.stack([xp.all(a == b) for a, b in zip(aa, bb, strict=True)]))


def _endpoint_charge(vm, state, p, delta, *, xp):
    patches = p.membrane_capacitance * vm
    capacitor = xp.concatenate(
        (
            ordered_scatter(
                patches, xp.zeros_like(p.initial_cell_charge_C), (p.membrane_cell,), xp=xp
            ),
            -ordered_scatter(
                patches, xp.zeros_like(p.initial_outside_charge_C), (p.membrane_outside,), xp=xp
            ),
        )
    )
    arguments = charged._charge_arguments(p, delta)
    actual = xp.concatenate((arguments.initial_cell_charge_C, arguments.initial_outside_charge_C))
    actual = actual + passive.charge_increment(state, p, xp=xp)
    required = p.field_active & ~xp.concatenate((xp.zeros_like(p.active), p.reservoir))
    return (
        xp.where(required, capacitor - actual, 0.0),
        field.CHARGE_ATOL_C + field.CHARGE_RTOL * xp.abs(actual),
    )


def evaluate(
    before,
    after,
    runtime_layout,
    protein_charge_increment_C,
    before_control,
    after_control,
    material_atol_fmol,
    *,
    implementation,
    xp=jnp,
    before_endpoint=None,
    after_endpoint=None,
):
    """Account one pre-admitted pair; ``valid`` does not publish a checkpoint.

    runtime_layout holds original anchors and the same admitted current P at
    both endpoints. Explicit protein charge is already physically projected.
    Numerical violations return raw arrays/flags; static structure errors raise.
    Shape/provenance, exact seed and clock admission stay with the host owner.
    Provider-created endpoint records allow separate device kernels. Complete
    source association, current domains and capacitor closure are rechecked;
    actual charged rate validity remains mandatory. This is not authorship.
    """
    if implementation not in view.IMPLEMENTATIONS.values():
        raise ValueError("Require a static exact ordinary implementation")
    if (before_endpoint is None) != (after_endpoint is None):
        raise ValueError("Supply both actual endpoint records or neither")
    if type(before) is not type(after) or before._fields != after._fields:
        raise ValueError("Require paired complete ordinary state arrays")
    p, b, e = runtime_layout, before, after
    for aa, bb in zip(b, e, strict=True):
        if aa.shape != bb.shape or aa.dtype != xp.float64 or bb.dtype != xp.float64:
            raise ValueError("Require paired float64 states with identical static shapes")
    delta, tolerance = xp.asarray(protein_charge_increment_C), xp.asarray(material_atol_fmol)
    if delta.shape != (p.active.size + p.outside_active.size,) or delta.dtype != xp.float64:
        raise ValueError("Require the padded float64 held-charge owner axis")
    if tolerance.shape != (b.amount_increment.shape[0],) or tolerance.dtype != xp.float64:
        raise ValueError("Require the original float64 species material tolerance axis")
    has_store, has_fuel = (
        hasattr(b, "chemical_amount_increment"),
        hasattr(b, "energy_amount_increment_fmol"),
    )
    balances, limits, checks = {}, {}, {}

    def record(name, value, limit):
        value, limit = xp.asarray(value), xp.asarray(limit)
        balances[name], limits[name] = value, limit
        checks[name] = xp.all(xp.isfinite(value)) & xp.all(xp.abs(value) <= limit)

    checks["material_tolerances_valid"] = xp.all(xp.isfinite(tolerance) & (tolerance > 0))
    endpoints = []
    zero = type(b)(*(xp.zeros_like(v) for v in b))
    ideals, fuel_ideals = _ideal_groups(b, e, p, has_store=has_store, has_fuel=has_fuel, xp=xp)
    pool_precision = xp.asarray(True)
    vms, group_roundoff = [], []
    supplied = (before_endpoint, after_endpoint)
    for label, state, control, endpoint in zip(
        ("before", "after"), (b, e), (before_control, after_control), supplied, strict=True
    ):
        if endpoint is None:
            endpoint = endpoint_values(
                state, control, p, delta, implementation=implementation, xp=xp
            )
        checks[label + "/endpoint_association"] = _association(
            endpoint, state, control, p, delta, xp=xp
        )
        vm, valid, grouping, domain = (
            endpoint.membrane_voltage_V,
            endpoint.charged_rates_valid,
            endpoint.charge_grouping_roundoff_C,
            endpoint.domain_valid & implementation.domain_valid(state, p, p.active, xp=xp),
        )
        charge_residual, charge_limit = _endpoint_charge(vm, state, p, delta, xp=xp)
        record(label + "/charged_endpoint", charge_residual, charge_limit)
        phi = endpoint.potential_V
        represented_vm = xp.where(
            p.membrane_active, phi[p.membrane_cell] - phi[p.active.size + p.membrane_outside], 0.0
        )
        record(label + "/endpoint_voltage_relation", vm - represented_vm, 0.0)
        record(
            label + "/endpoint_boundary",
            xp.where(p.reservoir, phi[p.active.size :] - p.boundary_V, 0.0),
            0.0,
        )
        checks[label + "/endpoint_potential_finite"] = xp.all(xp.isfinite(phi))
        checks[label + "/domain"], checks[label + "/charged_field_rates"] = domain, valid
        vms.append(vm)
        group_roundoff.append(grouping)
        current = _balances(state, p, has_store=has_store, has_fuel=has_fuel, xp=xp)
        bound = _limits(state, p, tolerance, xp=xp)
        if has_fuel:
            free, error, good, _, _ = _pool_change(
                zero, state, p, fuel_ideals[len(endpoints)], xp=xp
            )
            current["pool_energy"], extra = _pool_balance(zero, state, p, free, xp=xp)
            precise = xp.all(xp.abs(current["pool_energy"]) + error + extra <= fuel.ENERGY_ATOL_PJ)
            checks[label + "/pool_precision"] = good & precise
            pool_precision &= good & precise
        for name, value in current.items():
            record(label + "/" + name, value, bound[name])
        endpoints.append(current)
    for name in endpoints[0]:
        if name != "pool_energy":
            record(
                "interval/" + name,
                endpoints[1][name] - endpoints[0][name],
                xp.maximum(
                    _limits(b, p, tolerance, xp=xp)[name], _limits(e, p, tolerance, xp=xp)[name]
                ),
            )
    heat_limit = chemistry.ROUND_ATOL if implementation is view.calcium else 1e-12
    for name in b._fields:
        if name.endswith("_dissipated_energy_pJ"):
            for label, value in (
                ("before", getattr(b, name)),
                ("after", getattr(e, name)),
                ("interval", getattr(e, name) - getattr(b, name)),
            ):
                record(label + "/nondecreasing/" + name, xp.minimum(value, 0.0), heat_limit)
    er_electric, er_gross = xp.asarray(0.0), xp.asarray(0.0)
    er_capacitor_valid = xp.asarray(True)
    if has_store:
        for i in range(p.er_initial_amount.shape[0]):
            sb, se, c = (
                calcium.store_state(b, i),
                calcium.store_state(e, i),
                calcium.store_layout(p, i),
            )
            charge_fmol = xp.sum(
                c.valence * (se.amount_increment[:, c.er] - sb.amount_increment[:, c.er])
            )
            vb = calcium.er.voltage(sb, c, xp=xp)
            linear = _scaled_product((1e12, CHARGE_PER_FMOL, charge_fmol, vb), xp=xp)
            quadratic = _scaled_product(
                (0.5e12, CHARGE_PER_FMOL, CHARGE_PER_FMOL, charge_fmol, charge_fmol),
                (c.capacitance,),
                xp=xp,
            )
            change = linear[0] + quadratic[0]
            er_capacitor_valid &= ~(linear[2] | quadratic[2])
            er_capacitor_valid &= ~((linear[1] | quadratic[1]) & (change == 0) & (charge_fmol != 0))
            er_electric += change
            er_gross += xp.abs(change)
    chemical = sum(xp.sum(value.value_pJ) for value in ideals)
    chemical_bound = sum(xp.sum(value.rounding_bound_pJ) for value in ideals)
    ideal_valid = xp.all(xp.stack([xp.all(value.valid) for value in ideals]))
    difference = e._replace(
        amount_increment=e.amount_increment - b.amount_increment,
        extracellular_amount_increment=e.extracellular_amount_increment
        - b.extracellular_amount_increment,
    )
    _, _, dv = passive.capacitor_change(difference, p, xp=xp)
    plasma_linear = _scaled_product((1e12, p.membrane_capacitance, dv, vms[0]), xp=xp)
    plasma_quadratic = _scaled_product((0.5e12, p.membrane_capacitance, dv, dv), xp=xp)
    plasma_terms = plasma_linear[0] + plasma_quadratic[0]
    plasma = xp.sum(plasma_terms)
    actual_plasma = xp.sum(0.5e12 * p.membrane_capacitance * (vms[1] - vms[0]) * (vms[1] + vms[0]))
    heat = sum(
        xp.sum(getattr(e, name) - getattr(b, name))
        for name in b._fields
        if name.endswith("_dissipated_energy_pJ")
    )
    reservoir = xp.sum(e.reservoir_work_pJ - b.reservoir_work_pJ)
    electrode = xp.sum(e.electrode_work_pJ - b.electrode_work_pJ)
    pool, regeneration, metabolic, pool_bound = (xp.asarray(0.0) for _ in range(4))
    pool_valid = xp.asarray(True)
    if has_fuel:
        free, error, pool_valid, _, _ = _pool_change(b, e, p, fuel_ideals[2], xp=xp)
        pool, pool_bound = xp.sum(free), xp.sum(error)
        internal, internal_bound = _pool_balance(b, e, p, free, xp=xp)
        record("interval/pool_energy", internal, fuel.ENERGY_ATOL_PJ)
        checks["interval/pool_precision"] = pool_valid & xp.all(
            xp.abs(internal) + error + internal_bound <= fuel.ENERGY_ATOL_PJ
        )
        regeneration = xp.sum(e.regeneration_supplied_work_pJ - b.regeneration_supplied_work_pJ)
    else:
        metabolic = sum(
            (
                xp.sum(getattr(e, name) - getattr(b, name))
                for name in (
                    "metabolic_work_pJ",
                    "plasma_metabolic_work_pJ",
                    "er_metabolic_work_pJ",
                )
                if hasattr(b, name)
            ),
            xp.asarray(0.0),
        )
    terms = dict(
        chemical_change_pJ=chemical,
        plasma_capacitor_change_pJ=plasma,
        er_capacitor_change_pJ=er_electric,
        fuel_chemical_change_pJ=pool,
        dissipated_energy_pJ=heat,
        reservoir_work_pJ=reservoir,
        electrode_work_pJ=electrode,
        external_metabolic_work_pJ=metabolic,
        regeneration_supplied_work_pJ=regeneration,
    )
    residual = (
        chemical
        + plasma
        + er_electric
        + pool
        + heat
        - reservoir
        - electrode
        - metabolic
        - regeneration
    )
    energy_limit = calcium.ENERGY_ATOL_PJ if has_store else passive.ENERGY_ATOL_PJ
    gross = sum(xp.abs(value) for value in terms.values()) + xp.sum(xp.abs(plasma_terms)) + er_gross
    roundoff_bound = chemical_bound + pool_bound + 256 * EPS * gross
    record("interval/energy", residual, energy_limit)
    checks["interval/chemical_representable"] = ideal_valid
    checks["interval/fuel_representable"] = pool_valid & pool_precision
    ionic_fmol = xp.concatenate(
        (
            xp.sum(p.valence * difference.amount_increment, axis=0),
            xp.sum(p.valence * difference.extracellular_amount_increment, axis=0),
        )
    )
    ionic_q = passive.charge_increment(difference, p, xp=xp)
    map_underflow = xp.any((ionic_fmol != 0) & (ionic_q == 0)) | (
        xp.any(ionic_q != 0) & xp.all(dv == 0)
    )
    plasma_valid = ~xp.any(plasma_linear[2] | plasma_quadratic[2]) & ~xp.any(
        (plasma_linear[1] | plasma_quadratic[1]) & (plasma_terms == 0) & (dv != 0)
    )
    checks["interval/capacitor_representable"] = er_capacitor_valid & plasma_valid & ~map_underflow
    checks["interval/energy_precision"] = xp.isfinite(roundoff_bound) & (
        xp.abs(residual) + roundoff_bound <= energy_limit
    )
    # Dict pytrees reconstruct keys lexicographically after JIT. Keep the
    # failure index in that same public order on NumPy and compiled backends.
    checks = {key: checks[key] for key in sorted(checks)}
    statuses = xp.stack(tuple(checks.values()))
    first_bad = xp.min(xp.where(statuses, statuses.size, xp.arange(statuses.size)))
    diagnostics = dict(
        roundoff_bound_pJ=roundoff_bound,
        chemical_roundoff_bound_pJ=chemical_bound,
        actual_endpoint_plasma_change_pJ=actual_plasma,
        plasma_endpoint_roundoff_pJ=plasma - actual_plasma,
        plasma_voltage_increment_V=dv,
        actual_endpoint_voltage_increment_V=vms[1] - vms[0],
        protein_charge_increment_C=delta,
        before_charge_grouping_roundoff_C=group_roundoff[0],
        after_charge_grouping_roundoff_C=group_roundoff[1],
        chemical_underflow=xp.any(xp.stack([xp.any(v.underflow) for v in ideals])),
        chemical_overflow=xp.any(xp.stack([xp.any(v.overflow) for v in ideals])),
        chemical_cancellation_ambiguous=xp.any(
            xp.stack([xp.any(v.cancellation_ambiguous) for v in ideals])
        ),
        capacitor_map_underflow=map_underflow,
        capacitor_representable=er_capacitor_valid & plasma_valid & ~map_underflow,
    )
    return ArrayIntervalAccounting(
        xp.all(statuses), balances, limits, checks, terms, diagnostics, first_bad
    )
