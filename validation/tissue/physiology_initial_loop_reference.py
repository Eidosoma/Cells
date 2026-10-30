"""Independent initialization tape continuation and carried ordinary full loops."""

from copy import deepcopy

from validation.tissue import physiology_initial_preparation_reference as initial
from validation.tissue import physiology_tissue_loop_reference as loops
from validation.tissue.physiology_protein_packet_provider_reference import _mt_uniforms


def history(provenance, *, calls=2, refinement=1):
    raw, binding = provenance["definition"], provenance["binding"]
    request = provenance["request"]
    start = initial.evaluate(request, raw)
    options = request["component"]
    component = dict(
        protein={
            domain + "_mol_m3": [
                options["protein_mol_m3"][domain][owner]
                for owner in binding["inputs"][domain + "_ids"]
            ]
            for domain in ("cell", "membrane", "environment")
        },
        diffusion={name: start[name] for name in ("current_m2_s", "base_m2_s", "scheduled_m2_s")},
        controls=deepcopy(options["controls"]),
        time_s=0.0,
        loop_calls=0,
        stream_next_tick=options["next_tick"] + 1,
    )
    physical = initial.physical.reconstruct(raw, binding, start["current_m2_s"])
    oracle = initial.physical.ORACLES[raw["model"]["id"]]
    context = oracle.bind(physical)
    fields = oracle.unpack(context, oracle.initial(context))
    initial_fields = deepcopy(fields)
    native = deepcopy(start["numpy_successor"])
    controls = component["controls"]
    enabled = (
        controls["phase"] == "SIM"
        and controls["solver"] == "normal"
        and controls["dynamic_enabled"]
        and controls["protein_enabled"]
    )
    records = []
    for index in range(calls):
        packet = None
        if enabled:
            packet, native = _mt_uniforms(native, len(binding["inputs"]["membrane_ids"]))
        result = loops.advance(
            raw, fields, binding, component, packet, loop_index=index, refinement=refinement
        )
        component, fields = result["component"], result["fields"]
        records.append(
            dict(
                component=component,
                fields=fields,
                state=result["state"],
                endpoint_potential_V=result["endpoint_potential_V"],
                end_time_s=result["end_time_s"],
                packet=packet,
                numpy_successor=deepcopy(native),
                intervals=[
                    {k: v for k, v in row.items() if k != "context"} for row in result["intervals"]
                ],
            )
        )
    return dict(
        initialization=start,
        initial_fields=initial_fields,
        records=records,
        refinement=refinement,
        additional_biological_cases=0,
    )
