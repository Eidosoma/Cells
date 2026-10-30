"""Independent complete fields and direct electrical endpoint functionals.

No Cells/JAX imports or production slot maps. Full-node RHS roots use actual
held protein charge grouping. Raw named geometry assembles capacitance, and
100-digit direct energies plus endpoint electrode readouts form the oracle.
"""

from decimal import Context, Decimal, localcontext

import numpy as np

from validation.tissue import physiology_protein_charge_rhs_reference as rhs
from validation.tissue import physiology_protein_projection_reference as projection
from validation.tissue import surface_field_reference as electrical
from validation.tissue.surface_reference import F


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
):
    endpoints = []
    ion = raw["model"].get("ionic", raw["model"])
    for protein in (before_protein, after_protein):
        context, _, phi, proof = rhs.evaluate(
            raw,
            state,
            binding,
            current_diffusion,
            held_control,
            charge_reference,
            protein,
            valence=valence,
        )
        oracle = rhs.permeability.ORACLES[raw["model"]["id"]]
        fields = oracle.unpack(context, oracle.flatten(context, state))
        n = len(ion["cells"])
        z = np.asarray(context["layout"]["valence"])
        actual = np.r_[context["qi"], context["qo"]] + F * 1e-15 * np.sum(
            z * np.c_[fields["amount_increment"], fields["extracellular_amount_increment"]], axis=0
        )
        top = dict(
            layout=context["layout"],
            gauge_mask=[p["id"] == ion["closure"]["gauge_reference"] for p in ion["extracellular"]],
        )
        matrix, _, _, _, _, _ = electrical.topology(top)
        cap = matrix @ phi
        electrode = np.where(
            [p["reservoir"] for p in ion["extracellular"]], cap[n:] - actual[n:], 0.0
        )
        endpoints.append(
            dict(
                phi=phi,
                actual=actual,
                cap=cap,
                electrode=electrode,
                protein_charge=proof["held_protein_charge_C"],
                proof=proof,
            )
        )
    first, last = endpoints
    n = len(ion["cells"])
    cells = [p["id"] for p in ion["cells"]]
    outside = [p["id"] for p in ion["extracellular"]]
    change = projection.delta(
        raw, binding, before_protein, after_protein, valence=valence, faraday_C_mol=F
    )
    requested = np.asarray(
        [change["cell"][name]["charge_delta_C"] for name in cells]
        + [change["environment"][name]["charge_delta_C"] for name in outside]
    )
    represented = last["actual"] - first["actual"]
    dphi = last["phi"] - first["phi"]
    matrix_delta = matrix @ dphi
    reservoir = np.asarray([p["reservoir"] for p in ion["extracellular"]])
    primary_electrode = np.where(reservoir, matrix_delta[n:] - represented[n:], 0.0)
    saved_electrode = last["electrode"] - first["electrode"]
    with localcontext(Context(prec=100)):
        energy = []
        for patch in ion["membranes"]:
            i, j = cells.index(patch["inside"]), n + outside.index(patch["outside"])
            v0, v1 = _d(first["phi"][i] - first["phi"][j]), _d(last["phi"][i] - last["phi"][j])
            energy.append(Decimal("5e11") * _d(patch["capacitance_F"]) * (v1**2 - v0**2))
        work = [
            Decimal("1e12") * _d(row["boundary_potential_V"]) * _d(saved_electrode[i])
            if row["reservoir"]
            else Decimal(0)
            for i, row in enumerate(ion["extracellular"])
        ]
        cap_total, clamp_total = sum(energy, Decimal(0)), sum(work, Decimal(0))
        material = Decimal("1e12") * sum(
            (
                (_d(a) + _d(b)) / 2 * _d(q)
                for a, b, q in zip(first["phi"], last["phi"], represented, strict=True)
            ),
            Decimal(0),
        )
        return dict(
            capacitor_energy_change_pJ=float(cap_total),
            membrane_capacitor_energy_change_pJ=np.asarray([float(v) for v in energy]),
            clamp_work_pJ=float(clamp_total),
            electrode_work_pJ=np.asarray([float(v) for v in work]),
            electrode_charge_change_C=saved_electrode,
            primary_electrode_charge_change_C=primary_electrode,
            saved_electrode_charge_change_C=saved_electrode,
            represented_material_charge_change_C=represented,
            requested_material_charge_change_C=requested,
            charge_input_roundoff_C=represented - requested,
            stored_reference_increment_change_C=last["protein_charge"] - first["protein_charge"],
            midpoint_material_work_pJ=float(material),
            electrical_requirement_pJ=float(cap_total - clamp_total),
            gauge_work_coefficient_C=-float(np.sum(saved_electrode)),
            before_potential_V=first["phi"],
            after_potential_V=last["phi"],
            before_actual_charge_C=first["actual"],
            after_actual_charge_C=last["actual"],
            field_proofs=[point["proof"] for point in endpoints],
            exact_capacitor_energy_change_pJ=str(cap_total),
            exact_clamp_work_pJ=str(clamp_total),
            method="independent full-node roots/direct endpoint energy and electrode readouts",
            heat_inferred=False,
            driving_law_inferred=False,
        )
