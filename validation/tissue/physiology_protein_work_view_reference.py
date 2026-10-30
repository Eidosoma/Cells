"""Independent fixed-ion endpoint work from full-node fields and Decimal stocks.

No production imports. Protein remains a finite material owner at ionic
reservoirs. Field roots, direct electrode readouts and high-precision energy
differences give a comparison distinct from production's stable delta algebra.
"""

from decimal import Decimal, localcontext

import numpy as np

from validation.tissue import physiology_protein_charge_view_reference as fields
from validation.tissue.surface_reference import R


def evaluate(
    raw,
    state,
    binding,
    current_diffusion,
    held_control,
    charge_reference,
    before,
    after,
    *,
    valence,
    standard_concentration_mol_m3,
):
    first = fields.evaluate(
        raw,
        state,
        binding,
        current_diffusion,
        held_control,
        charge_reference,
        before,
        valence=valence,
    )
    last = fields.evaluate(
        raw,
        state,
        binding,
        current_diffusion,
        held_control,
        charge_reference,
        after,
        valence=valence,
    )
    model = raw["model"].get("ionic", raw["model"])
    with localcontext() as context:
        context.prec = 100

        def number(value):
            return Decimal.from_float(float(value))

        standard = number(standard_concentration_mol_m3)
        if not standard.is_finite() or standard <= 0:
            raise ValueError("Declare a finite positive ideal standard concentration")
        rt = number(R) * number(model["temperature_K"])
        chemical_terms = []
        for domain, axis, owners in (
            ("cell_mol_m3", "cell_ids", model["cells"]),
            ("environment_mol_m3", "environment_ids", model["extracellular"]),
        ):
            names = binding["inputs"][axis]
            for owner in owners:
                i = names.index(owner["id"])

                def density(value):
                    c = number(value)
                    return Decimal(0) if c == 0 else c * ((c / standard).ln() - 1)

                volume = number(owner["volume_pL"]) * Decimal("1e-15")
                chemical_terms.append(
                    rt
                    * volume
                    * (density(after[domain][i]) - density(before[domain][i]))
                    * Decimal("1e12")
                )
        capacitor_terms = []
        for i, membrane in enumerate(model["membranes"]):
            v0 = number(first["after"]["membrane_voltage_V"][i])
            v1 = number(last["after"]["membrane_voltage_V"][i])
            capacitor_terms.append(
                Decimal("0.5e12") * number(membrane["capacitance_F"]) * (v1 * v1 - v0 * v0)
            )
        clamp_terms = []
        for i, owner in enumerate(model["extracellular"]):
            dq = number(last["after"]["electrode_charge_C"][i]) - number(
                first["after"]["electrode_charge_C"][i]
            )
            clamp_terms.append(
                Decimal("1e12") * number(owner["boundary_potential_V"]) * dq
                if owner["reservoir"]
                else Decimal(0)
            )
        chemical, capacitor, clamp = (
            sum(values, Decimal(0)) for values in (chemical_terms, capacitor_terms, clamp_terms)
        )
        return dict(
            chemical_energy_change_pJ=float(chemical),
            owner_chemical_energy_change_pJ=np.array([float(v) for v in chemical_terms]),
            capacitor_energy_change_pJ=float(capacitor),
            membrane_capacitor_energy_change_pJ=np.array([float(v) for v in capacitor_terms]),
            clamp_work_pJ=float(clamp),
            electrode_work_pJ=np.array([float(v) for v in clamp_terms]),
            conditional_reversible_work_pJ=float(chemical + capacitor - clamp),
            before_potential_V=first["after"]["potential_V"],
            after_potential_V=last["after"]["potential_V"],
        )
