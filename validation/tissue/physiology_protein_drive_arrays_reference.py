"""Independent SI endpoint work and 4096-digit declared energy arithmetic.

No Cells/JAX imports or production array reductions. Physical tolerances are
the four ordinary family constants; numerical precision refusals are separate.
"""

from decimal import Context, Decimal, localcontext

import numpy as np

from validation.tissue import physiology_protein_work_arrays_reference as work

LIMITS = dict(passive=2e-8, ionic=2e-8, calcium=1e-9, fuel=1e-9)
FAMILIES = {
    "resolved_tissue@1": "passive",
    "resolved_tissue@12": "ionic",
    "resolved_calcium@11": "calcium",
    "resolved_calcium_energy@5": "fuel",
}


def _d(value):
    return Decimal.from_float(float(value))


def balance(
    chemical_change_pJ,
    capacitor_change_pJ,
    clamp_work_pJ,
    external_work_pJ,
    dissipated_free_energy_pJ,
    *,
    family,
):
    values = (
        chemical_change_pJ,
        capacitor_change_pJ,
        dissipated_free_energy_pJ,
        -clamp_work_pJ,
        -external_work_pJ,
    )
    if family not in LIMITS or not np.isfinite(values).all():
        raise ValueError("Independent finite scalar energies and exact ordinary family required")
    with localcontext(Context(prec=4096)):
        residual = sum((_d(value) for value in values), Decimal(0))
        shown = float(residual)
        if not np.isfinite(shown):
            raise ValueError("Independent residual display overflows")
        limit = LIMITS[family]
        return dict(
            balance_residual_pJ=shown,
            balance_residual_pJ_exact=str(residual),
            physical_energy_tolerance_pJ=limit,
            original_physical_energy_budget=bool(abs(shown) <= limit),
            nonnegative_declared_dissipation=bool(dissipated_free_energy_pJ >= 0),
            valid=bool(dissipated_free_energy_pJ >= 0 and abs(shown) <= limit),
        )


def evaluate(
    raw,
    state,
    binding,
    current_diffusion,
    held_control,
    charge_reference,
    before_protein,
    after_protein,
    *,
    external_work_pJ,
    dissipated_free_energy_pJ,
    budget_provenance,
    valence,
    faraday_C_mol,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K,
):
    if type(budget_provenance) is not str or not budget_provenance.strip():
        raise ValueError("Independent explicit declared-budget provenance required")
    conditional = work.evaluate(
        raw,
        state,
        binding,
        current_diffusion,
        held_control,
        charge_reference,
        before_protein,
        after_protein,
        valence=valence,
        faraday_C_mol=faraday_C_mol,
        temperature_K=temperature_K,
        standard_concentration_mol_m3=standard_concentration_mol_m3,
        gas_constant_J_mol_K=gas_constant_J_mol_K,
    )
    declared = balance(
        conditional["chemical_energy_change_pJ"],
        conditional["capacitor_energy_change_pJ"],
        conditional["clamp_work_pJ"],
        external_work_pJ,
        dissipated_free_energy_pJ,
        family=FAMILIES[raw["model"]["id"]],
    )
    with localcontext(Context(prec=4096)):
        independent_si = (
            Decimal(conditional["chemical"]["total_free_energy_change_pJ_exact"])
            + Decimal(conditional["electrical"]["exact_capacitor_energy_change_pJ"])
            + _d(dissipated_free_energy_pJ)
            - Decimal(conditional["electrical"]["exact_clamp_work_pJ"])
            - _d(external_work_pJ)
        )
        return dict(
            conditional_work=conditional,
            energy_balance=declared,
            direct_SI_residual_pJ=float(independent_si),
            direct_SI_residual_pJ_exact=str(independent_si),
            valid=bool(conditional["strict_conservation_valid"] and declared["valid"]),
            heat_inferred=False,
            driving_law_inferred=False,
            loop_acceptance=False,
        )
