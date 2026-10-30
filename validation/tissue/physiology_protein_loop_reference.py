"""Independent carried ionic integrations and prescribed protein packets.

No Cells/JAX imports. Each later loop starts from this reference's own ionic
and protein endpoint. RNG packets are prescribed inputs, not independent RNG
evidence. Both tolerance settings carry their complete histories separately.
"""

from validation.tissue import physiology_permeability_schedule_reference as schedules
from validation.tissue import physiology_protein_charge_interval_reference as ionic
from validation.tissue import physiology_protein_transition_reference as protein
from validation.tissue.physiology_tissue_loop_reference import component_transition


def integrate(
    raw,
    fields,
    binding,
    source_component,
    charge_reference,
    loops,
    *,
    valence,
    standard_concentration_mol_m3,
    refinement=1,
    schedule=None,
):
    carried, component, endpoints = fields, source_component, []
    for item in loops:
        if schedule is not None:
            component = schedules.stage(
                schedule, binding, source_component, component, item["loop_index"]
            )
        # The separate component reference computes finalization without drawing.
        held = component_transition(binding, component, item["prescribed_uniforms"])
        solved = ionic.integrate(
            raw,
            carried,
            binding,
            held["diffusion"]["current_m2_s"],
            charge_reference,
            component["protein"],
            valence=valence,
            intervals=item["intervals"],
            refinement=refinement,
        )
        carried = solved["endpoints"][-1]["fields"]
        updated = protein.evaluate(
            raw,
            carried,
            binding,
            component,
            charge_reference,
            item["prescribed_uniforms"],
            item["intervals"][-1]["endpoint_control"],
            valence=valence,
            standard_concentration_mol_m3=standard_concentration_mol_m3,
        )
        component = updated["component"]
        endpoints.append(
            dict(
                fields=carried,
                state=solved["endpoints"][-1]["state"],
                context=solved["endpoints"][-1]["context"],
                component=component,
                potential_V=updated["potential_V"],
                work=updated["work"],
                evaluations=sum(row["evaluations"] for row in solved["endpoints"]),
            )
        )
    return dict(endpoints=endpoints, refinement=refinement)
