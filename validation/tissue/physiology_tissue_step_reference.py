"""Independent full-interval held-P tissue integration, without Cells/JAX.

The prior independent named-owner unit reconstruction and complete ordinary
oracles supply rates. Source schedules choose the held packet at the original
interval start; DOP853 integrates its entire declared interval with fixed P.
"""

import math

import numpy as np
from scipy.integrate import solve_ivp

from validation.tissue import physiology_permeability_view_reference as view


class ReferenceStepError(RuntimeError):
    def __init__(self, reason, evidence):
        super().__init__(reason)
        self.evidence = evidence


def grid(raw):
    e, x = raw["experiment"], raw["execution"]
    dt, end = float(x["dt"]), float(e["end_time"])
    if not np.isfinite([dt, end]).all() or min(dt, end) <= 0:
        raise ValueError("Require an explicit positive source grid")
    count = math.ceil(end / dt)
    if count > x["max_steps"]:
        raise ValueError("Source nominal grid exceeds its declared step cap")
    events = {0.0, end, *(i * dt for i in range(1, count) if i * dt < end)}
    for key, groups in e.items():
        if key.endswith("_controls"):
            events.update(
                row["time"]
                for group in groups
                for row in group.get("schedule", group.get("controls", []))
            )
    result = sorted(events)
    if len(result) - 1 > x["max_steps"]:
        raise ValueError("Source event grid exceeds its declared step cap")
    return result


def integrate(
    raw, fields, binding_record, current_diffusion_m2_s, *, start_time_s, end_time_s, refinement=1
):
    points = grid(raw)
    if (
        type(refinement) is not int
        or refinement < 1
        or start_time_s not in points
        or end_time_s not in points
        or points.index(end_time_s) != points.index(start_time_s) + 1
    ):
        raise ValueError("Reference must cover exactly the next original grid/control interval")
    effective = view.reconstruct(raw, binding_record, current_diffusion_m2_s)
    oracle = view.ORACLES[raw["model"]["id"]]
    context = oracle.bind(effective)
    initial = oracle.flatten(context, fields)
    if not np.isfinite(initial).all():
        raise ValueError("Complete source state must be finite")
    interval = float(end_time_s - start_time_s)
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
            # The time argument selects the held source packet, not a new
            # schedule value during an adaptive internal trial at the endpoint.
            return oracle.evaluate(context, state, start_time_s)[0]
        except Exception as error:
            raise ReferenceStepError(
                str(error),
                dict(
                    time_s=float(time),
                    state=state.tolist(),
                    held_control_time_s=start_time_s,
                    end_time_s=end_time_s,
                    evaluations=evaluations,
                    automatic_retry=False,
                ),
            ) from error

    solved = solve_ivp(
        rhs,
        (start_time_s, end_time_s),
        initial,
        method="DOP853",
        rtol=2e-11 / refinement,
        atol=atol,
        max_step=interval / (4 * refinement),
        first_step=interval / (8 * refinement),
    )
    if not solved.success:
        raise ReferenceStepError(
            solved.message,
            dict(
                time_s=float(solved.t[-1]),
                state=solved.y[:, -1].tolist(),
                evaluations=evaluations,
                automatic_retry=False,
            ),
        )
    rate, potential, proof = oracle.evaluate(context, solved.y[:, -1], end_time_s)
    return dict(
        context=context,
        state=solved.y[:, -1],
        endpoint_rate=rate,
        endpoint_potential_V=potential,
        endpoint_proof=proof,
        start_time_s=start_time_s,
        end_time_s=end_time_s,
        interval_s=interval,
        evaluations=evaluations,
        refinement=refinement,
        rtol=2e-11 / refinement,
        state_atol=2e-14 / refinement,
        charge_atol_C=1e-29 / refinement,
        max_step_s=interval / (4 * refinement),
        method="DOP853 on exact original held-P interval",
    )
