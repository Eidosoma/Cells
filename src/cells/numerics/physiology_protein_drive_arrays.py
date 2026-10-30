"""Numerical admission of explicitly declared protein work and dissipation.

The public wrapper recomputes the complete associated conditional endpoint
work. A numerical bound never enlarges the original family energy tolerance.
Declarations supply no inferred physical drive/heat law or loop acceptance.
"""

from typing import NamedTuple

import jax.numpy as jnp

from cells.core import physiology_protein_chemical_arrays as chemical
from cells.models import physiology_permeability_view as view
from cells.numerics import physiology_protein_work_arrays as endpoint_work
from cells.numerics.physiology_protein_interval_arrays import _two_sum

EPS = 2.220446049250313e-16


class DeclaredEnergyBalance(NamedTuple):
    valid: object
    external_work_pJ: object
    dissipated_free_energy_pJ: object
    raw_terms_pJ: object
    declaration_difference_expansion_pJ: object
    residual_expansion_pJ: object
    residual_high_pJ: object
    residual_low_pJ: object
    balance_residual_pJ: object
    physical_energy_tolerance_pJ: object
    normalized_energy_residual: object
    numerical_addition_bound_pJ: object
    checks: object


class DeclaredDriveAdmission(NamedTuple):
    valid: object
    conditional_work: object
    energy_balance: object
    numerical_bound_pJ: object
    checks: object


def _energy_limit(implementation):
    if implementation not in view.IMPLEMENTATIONS.values():
        raise ValueError("Require an exact ordinary static model implementation")
    return (
        view.passive.ENERGY_ATOL_PJ
        if implementation in (view.passive, view.ionic)
        else view.calcium.ENERGY_ATOL_PJ
    )


def _normal_quantum(value, *, xp):
    # EFT errors are integer multiples of the inputs' last set binary bits.
    # Requiring that quantum to be normal prevents silent backend loss of
    # subnormal intermediate remainders, while exact power-of-two tiny inputs
    # can still pass. This is precision admission, not a physical energy floor.
    safe = xp.where(xp.isfinite(value), xp.abs(value), 0.0)
    mantissa, exponent = xp.frexp(safe)
    significand = (mantissa * 9007199254740992.0).astype(xp.uint64)
    count = xp.clip(-969 - exponent, 0, 53).astype(xp.uint64)
    mask = (xp.uint64(1) << count) - xp.uint64(1)
    return (significand & mask) == 0


def _expansion(terms, *, xp):
    # Fixed five-term grow-expansion: retain every two-sum remainder instead
    # of collapsing a small imbalance into huge cancelling declarations.
    partials = []
    for i in range(terms.size):
        carry = terms[i]
        next_partials = []
        for part in partials:
            carry, remainder = _two_sum(carry, part, xp=xp)
            next_partials.append(remainder)
        partials = [*next_partials, carry]
    return xp.stack(partials)


def _balance(
    chemical_change_pJ,
    capacitor_change_pJ,
    clamp_work_pJ,
    external_work_pJ,
    dissipated_free_energy_pJ,
    *,
    implementation,
    xp,
):
    """Private five-scalar arithmetic; not an endpoint-admission interface."""
    values = tuple(
        xp.asarray(v)
        for v in (
            chemical_change_pJ,
            capacitor_change_pJ,
            clamp_work_pJ,
            external_work_pJ,
            dissipated_free_energy_pJ,
        )
    )
    if any(v.shape != () or v.dtype != xp.float64 for v in values):
        raise ValueError("Require explicit scalar float64 pJ energy inputs")
    g, u, clamp, external, dissipated = values
    limit = xp.asarray(_energy_limit(implementation), dtype=xp.float64)
    raw_terms = xp.stack((g, u, dissipated, -clamp, -external))
    difference, difference_low = _two_sum(dissipated, -external, xp=xp)
    expansion = _expansion(xp.stack((g, u, -clamp, difference, difference_low)), xp=xp)
    high, low = chemical._sum_pair(expansion, xp=xp)
    residual = high + low
    # Scale before reduction: summing huge absolute declarations first could
    # overflow even when their exact difference and the final residual resolve.
    scaled_bound = chemical._product((64 * EPS, xp.abs(raw_terms)), xp=xp)[0]
    bound_high, bound_low = chemical._sum_pair(scaled_bound, xp=xp)
    bound = chemical._bound(bound_high + bound_low, xp.any(raw_terms != 0), xp=xp)
    finite = xp.all(xp.isfinite(raw_terms))
    normal = ~xp.any(chemical._subnormal(raw_terms, xp=xp))
    component_quantum = xp.all(_normal_quantum(xp.stack((g, u, clamp)), xp=xp))
    # Exactly equal declarations cancel before any EFT arithmetic with work.
    declaration_quantum = (dissipated == external) | xp.all(
        _normal_quantum(xp.stack((dissipated, external)), xp=xp)
    )
    arithmetic_finite = xp.all(xp.isfinite(expansion)) & xp.all(
        xp.isfinite(xp.stack((difference, difference_low, high, low, residual, bound)))
    )
    checks = dict(
        finite_energy_inputs=finite,
        nonnegative_declared_dissipation=dissipated >= 0,
        normal_energy_inputs=normal,
        normal_expansion_quantum=component_quantum & declaration_quantum,
        finite_arithmetic=arithmetic_finite,
        residual_display_representable=(residual != 0) | xp.all(expansion == 0),
        original_physical_energy_budget=xp.isfinite(residual) & (xp.abs(residual) <= limit),
    )
    checks = {key: checks[key] for key in sorted(checks)}
    return DeclaredEnergyBalance(
        xp.all(xp.stack(tuple(checks.values()))),
        external,
        dissipated,
        raw_terms,
        xp.stack((difference, difference_low)),
        expansion,
        high,
        low,
        residual,
        limit,
        xp.abs(residual) / limit,
        bound,
        checks,
    )


def evaluate(
    charge_reference,
    before_protein,
    after_protein,
    before_endpoint,
    after_endpoint,
    geometry,
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
    xp=jnp,
):
    """Check an associated endpoint transition against a declared energy budget.

    External work is finite and signed; declared dissipation is nonnegative.
    Both are explicit scalar float64 pJ inputs. Provenance is a required static
    nonempty declaration, not authentication or evidence of a physical law.
    Recompute the frozen complete-input work contract; preserve every refusal.
    No field solve, random draw, state publication or loop acceptance occurs.
    """
    if type(budget_provenance) is not str or not budget_provenance.strip():
        raise ValueError("Require explicit static nonempty declared-budget provenance")
    work = endpoint_work.evaluate(
        charge_reference,
        before_protein,
        after_protein,
        before_endpoint,
        after_endpoint,
        geometry,
        valence=valence,
        faraday_C_mol=faraday_C_mol,
        temperature_K=temperature_K,
        standard_concentration_mol_m3=standard_concentration_mol_m3,
        gas_constant_J_mol_K=gas_constant_J_mol_K,
        implementation=implementation,
        xp=xp,
    )
    balance = _balance(
        work.chemical.total_free_energy_change_pJ,
        work.electrical.capacitor_energy_change_pJ,
        work.electrical.clamp_work_pJ,
        external_work_pJ,
        dissipated_free_energy_pJ,
        implementation=implementation,
        xp=xp,
    )
    numerical_bound = work.component_roundoff_bound_pJ + balance.numerical_addition_bound_pJ
    checks = dict(
        associated_conditional_work=work.valid,
        declared_energy_balance=balance.valid,
        finite_numerical_bound=xp.isfinite(numerical_bound),
        original_family=(
            hasattr(before_endpoint.source_state, "chemical_amount_increment")
            == (implementation in (view.calcium, view.fuel))
        ),
    )
    checks = {key: xp.asarray(checks[key]) for key in sorted(checks)}
    return DeclaredDriveAdmission(
        xp.all(xp.stack(tuple(checks.values()))),
        work,
        balance,
        numerical_bound,
        checks,
    )
