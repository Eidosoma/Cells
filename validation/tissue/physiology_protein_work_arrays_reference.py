"""Independent SI conditional protein work under one named source contract.

Complete raw inputs independently generate the full-node field endpoints and
640-digit absolute chemical functionals. Actual named pL volumes convert once
to the binary64 SI volumes used by the binding; no production maps/receipts or
stable delta algebra is consumed. This module has no Cells/JAX imports.
"""

from decimal import Context, Decimal, localcontext

import numpy as np

from validation.tissue import physiology_protein_chemical_arrays_reference as chemical
from validation.tissue import physiology_protein_electrical_arrays_reference as electrical
from validation.tissue.surface_reference import F, R


def _d(value):
    return Decimal.from_float(float(value))


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
    valence,
    faraday_C_mol,
    temperature_K,
    standard_concentration_mol_m3,
    gas_constant_J_mol_K,
):
    model = raw["model"].get("ionic", raw["model"])
    if (
        faraday_C_mol != F
        or gas_constant_J_mol_K != R
        or temperature_K != model["temperature_K"]
        or not np.isfinite(valence)
    ):
        raise ValueError("Independent Cells SI parameter/source association mismatch")
    volumes = []
    for domain, owners in (("cell", model["cells"]), ("environment", model["extracellular"])):
        lookup = {owner["id"]: owner for owner in owners}
        names = binding["inputs"][domain + "_ids"]
        volumes.append([float(lookup[name]["volume_pL"]) * 1e-15 for name in names])
    thermodynamics = chemical.change(
        before_protein,
        after_protein,
        *volumes,
        temperature_K=temperature_K,
        standard_concentration_mol_m3=standard_concentration_mol_m3,
        gas_constant_J_mol_K=gas_constant_J_mol_K,
    )
    fields = electrical.evaluate(
        raw,
        state,
        binding,
        current_diffusion,
        held_control,
        charge_reference,
        before_protein,
        after_protein,
        valence=valence,
    )
    with localcontext(Context(prec=4096)):
        projections = []
        for before, after in (
            (charge_reference, before_protein),
            (charge_reference, after_protein),
            (before_protein, after_protein),
        ):
            amounts = [
                (_d(e) - _d(b)) * _d(v)
                for field, volume in zip(
                    ("cell_mol_m3", "environment_mol_m3"), volumes, strict=True
                )
                for b, e, v in zip(before[field], after[field], volume, strict=True)
            ]
            net = sum(amounts, Decimal(0))
            gross = sum((abs(v) for v in amounts), Decimal(0))
            projections.append(
                dict(
                    net_mol_exact=str(net),
                    gross_mol_exact=str(gross),
                    strict_conservation_valid=bool(abs(net) <= _d(3e-13) * gross),
                )
            )
        g = Decimal(thermodynamics["total_free_energy_change_pJ_exact"])
        capacitor = Decimal(fields["exact_capacitor_energy_change_pJ"])
        clamp = Decimal(fields["exact_clamp_work_pJ"])
        work = g + capacitor - clamp
        return dict(
            chemical_energy_change_pJ=float(g),
            capacitor_energy_change_pJ=float(capacitor),
            clamp_work_pJ=float(clamp),
            conditional_reversible_work_pJ=float(work),
            conditional_reversible_work_pJ_exact=str(work),
            strict_conservation_valid=all(v["strict_conservation_valid"] for v in projections),
            projections=projections,
            chemical=thermodynamics,
            electrical=fields,
            method=(
                "common named source; direct SI absolute functionals "
                "and independent full-node roots"
            ),
            heat_inferred=False,
            driving_law_inferred=False,
        )
