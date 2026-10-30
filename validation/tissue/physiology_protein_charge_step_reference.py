"""Independent local DOP853 interval with held protein, permeability and controls."""

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import physiology_protein_charge_rhs_reference as rates
from validation.tissue.physiology_tissue_step_reference import ReferenceStepError


def integrate(
    raw,
    fields,
    binding,
    current_diffusion,
    held_control,
    before,
    after,
    *,
    valence,
    duration_s,
    refinement=1,
):
    if (
        not np.isfinite(duration_s)
        or duration_s <= 0
        or type(refinement) is not int
        or refinement < 1
    ):
        raise ValueError("Declare a finite positive held interval and integer reference refinement")
    context, _, _, _ = rates.evaluate(
        raw, fields, binding, current_diffusion, held_control, before, after, valence=valence
    )
    oracle = rates.permeability.ORACLES[raw["model"]["id"]]
    initial = oracle.flatten(context, fields)
    atol = oracle.flatten(
        context,
        {
            name: np.full(shape, (1e-29 if name.endswith("_C") else 2e-14) / refinement)
            for name, shape in context["shapes"].items()
        },
    )
    evaluations = 0

    def rhs(time, state):
        nonlocal evaluations
        evaluations += 1
        try:
            return oracle.evaluate(context, state, 0.0)[0]
        except Exception as error:
            raise ReferenceStepError(
                str(error),
                dict(
                    time_s=float(time),
                    state=state.tolist(),
                    duration_s=duration_s,
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            ) from error

    solved = solve_ivp(
        rhs,
        (0.0, duration_s),
        initial,
        method="DOP853",
        rtol=2e-11 / refinement,
        atol=atol,
        max_step=duration_s / (4 * refinement),
        first_step=duration_s / (8 * refinement),
    )
    if not solved.success:
        raise ReferenceStepError(
            solved.message,
            dict(
                times_s=solved.t.tolist(),
                states=solved.y.tolist(),
                evaluations=evaluations,
                automatic_retry=False,
            ),
        )
    endpoint = solved.y[:, -1]
    _, phi, proof = oracle.evaluate(context, endpoint, 0.0)
    return dict(
        context=context,
        state=endpoint,
        endpoint_potential_V=phi,
        proof=proof,
        evaluations=evaluations,
        refinement=refinement,
        duration_s=duration_s,
    )
