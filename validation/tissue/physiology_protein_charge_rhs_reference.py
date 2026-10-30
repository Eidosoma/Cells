"""Independent complete held-protein RHS from named owners and full-node roots.

No production imports. Only plasma field-charge arguments in a private copy
acquire the independently projected protein increment. This copy is not a new
physical recipe or energy baseline. Original store/fuel definitions survive
the finite-fuel reference's live calcium-context reconstruction.
"""

import numpy as np

from validation.tissue import physiology_permeability_view_reference as permeability
from validation.tissue import physiology_protein_projection_reference as projection
from validation.tissue.surface_reference import F


def evaluate(raw, fields, binding, current_diffusion, held_control, before, after, *, valence):
    effective = permeability.reconstruct(raw, binding, current_diffusion, held_control)
    change = projection.delta(raw, binding, before, after, valence=valence, faraday_C_mol=F)
    model = effective["model"].get("ionic", effective["model"])
    delta, anchors = [], []
    for domain, rows in (("cell", model["cells"]), ("environment", model["extracellular"])):
        for row in rows:
            q = change[domain][row["id"]]["charge_delta_C"]
            delta.append(q)
            anchors.append(row["initial_charge_C"])
            # Carry through the fuel wrapper's fresh projection/bind, leaving
            # store definitions and all actual material owners unchanged.
            row["initial_charge_C"] += q
    oracle = permeability.ORACLES[raw["model"]["id"]]
    context = oracle.bind(effective)
    state = oracle.flatten(context, fields)
    derivative, phi, proof = oracle.evaluate(context, state, 0.0)
    return (
        context,
        derivative,
        phi,
        dict(
            proof,
            original_plasma_anchors_C=np.asarray(anchors),
            held_protein_charge_C=np.asarray(delta),
            field_arguments_only=True,
            coupled_trajectory=False,
        ),
    )
