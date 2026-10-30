"""Independent named contact mapping and complete ordinary physical RHS."""

from copy import deepcopy
from decimal import Decimal, localcontext

from validation.perturbations import global_controls_reference as setters
from validation.tissue import physiology_permeability_view_reference as physical


def prepare(raw, program, pairs, block_state, base_control, time_s, events_enabled):
    model = raw["model"].get("ionic", raw["model"])
    state = dict(temperature_K=model["temperature_K"], boundary_voltage_V=[0.0] * 4, **block_state)
    after = setters.evaluate(
        program, state, time_s, model["temperature_K"], events_enabled=events_enabled
    )
    if after["pump_available"] != 1 and not any(row.get("pump") for row in model["membranes"]):
        raise ValueError("Independent pump factor has no actual Na/K owners")
    output = deepcopy(base_control)
    component_ids = program["membrane_ids"]
    mapping = {j: (a, b) for j, a, b in pairs}
    with localcontext() as context:
        context.prec = 100

        def product(a, b):
            return float(Decimal.from_float(float(a)) * Decimal.from_float(float(b)))

        for index, edge in enumerate(model["junctions"]):
            sender, receiver = mapping[edge["id"]]
            a, b = (
                after["junction_available"][component_ids.index(name)]
                for name in (sender, receiver)
            )
            if a != b:
                raise ValueError("Independent physical contact factors disagree")
            output["junction"][index] = product(base_control["junction"][index], a)
        if "pump" in output:
            output["pump"] = [product(v, after["pump_available"]) for v in base_control["pump"]]
    return {k: after[k] for k in block_state}, output


def evaluate(
    raw,
    fields,
    binding_record,
    current_diffusion_m2_s,
    block_binding,
    block_state,
    base_control,
    time_s,
    events_enabled,
):
    after, control = prepare(
        raw,
        block_binding["program"],
        block_binding["junction_membranes"],
        block_state,
        base_control,
        time_s,
        events_enabled,
    )
    context, derivative, potential, proof = physical.evaluate(
        raw, fields, binding_record, current_diffusion_m2_s, control
    )
    return context, derivative, potential, dict(proof, block_state=after, effective_control=control)
