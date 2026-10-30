"""Independent prescribed-packet protein transition and evolved-state work.

No Cells/JAX imports. The component transform uses Decimal owner arithmetic;
fields use independent full-node roots, chemical energy uses direct Decimal
functionals, and complete shifted rates use the separate model references.
This validates a split operator, not an independently integrated full loop.
"""

from validation.tissue import physiology_protein_charge_rhs_reference as rates
from validation.tissue import physiology_protein_work_view_reference as work
from validation.tissue.physiology_tissue_loop_reference import component_transition


def evaluate(
    raw,
    fields,
    binding,
    source_component,
    charge_reference,
    prescribed_uniforms,
    endpoint_control,
    *,
    valence,
    standard_concentration_mol_m3,
):
    after = component_transition(binding, source_component, prescribed_uniforms)
    diffusion = after["diffusion"]["current_m2_s"]
    electrical = work.evaluate(
        raw,
        fields,
        binding,
        diffusion,
        endpoint_control,
        charge_reference,
        source_component["protein"],
        after["protein"],
        valence=valence,
        standard_concentration_mol_m3=standard_concentration_mol_m3,
    )
    context, derivative, potential, proof = rates.evaluate(
        raw,
        fields,
        binding,
        diffusion,
        endpoint_control,
        charge_reference,
        after["protein"],
        valence=valence,
    )
    return dict(
        component=after,
        work=electrical,
        context=context,
        derivative=derivative,
        potential_V=potential,
        proof=proof,
    )
