"""Independent carried held-charge trajectories across explicit control boundaries."""

from validation.tissue import physiology_protein_charge_step_reference as local


def integrate(
    raw, fields, binding, current_diffusion, before, after, *, valence, intervals, refinement=1
):
    """Carry the independent full state; never restart each interval from Cells."""
    if not intervals:
        raise ValueError("Require at least one explicit held-control interval")
    carried, endpoints = fields, []
    for interval in intervals:
        solved = local.integrate(
            raw,
            carried,
            binding,
            current_diffusion,
            interval["held_control"],
            before,
            after,
            valence=valence,
            duration_s=interval["duration_s"],
            refinement=refinement,
        )
        oracle = local.rates.permeability.ORACLES[raw["model"]["id"]]
        carried = oracle.unpack(solved["context"], solved["state"])
        _, _, right_phi, _ = local.rates.evaluate(
            raw,
            carried,
            binding,
            current_diffusion,
            interval["endpoint_control"],
            before,
            after,
            valence=valence,
        )
        endpoints.append(
            dict(
                context=solved["context"],
                state=solved["state"],
                fields=carried,
                held_potential_V=solved["endpoint_potential_V"],
                endpoint_potential_V=right_phi,
                evaluations=solved["evaluations"],
                duration_s=interval["duration_s"],
            )
        )
    return dict(endpoints=endpoints, refinement=refinement)
