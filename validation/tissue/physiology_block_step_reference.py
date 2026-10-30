"""Independent named-source blocker placement and full accepted-interval oracle."""

from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np
from scipy.integrate import solve_ivp

from validation.perturbations import global_controls_reference as setters
from validation.tissue import physiology_permeability_view_reference as physical
from validation.tissue.physiology_tissue_step_reference import ReferenceStepError, grid


def held_definition(raw, binding, diffusion, block_binding, block_state, *, control_time_s):
    """Select every original control by name, then alter only junction/NaK rates."""
    changed = physical.reconstruct(raw, binding, diffusion)
    model = changed["model"].get("ionic", changed["model"])
    experiment = changed["experiment"]
    for key, groups in experiment.items():
        if not key.endswith("_controls"):
            continue
        for group in groups:
            field = "controls" if "controls" in group else "schedule"
            selected = next(v for v in reversed(group[field]) if v["time"] <= control_time_s)
            group[field] = [deepcopy(selected) | dict(time=0.0)]
    names = block_binding["program"]["membrane_ids"]
    mapping = {j: (a, b) for j, a, b in block_binding["junction_membranes"]}
    with localcontext() as context:
        context.prec = 100

        def multiply(a, b):
            return float(Decimal.from_float(float(a)) * Decimal.from_float(float(b)))

        for group in experiment["junction_controls"]:
            pair = mapping[group["junction_id"]]
            a, b = (block_state["junction_available"][names.index(name)] for name in pair)
            if a != b:
                raise ValueError("Independent contact factors disagree")
            group["schedule"][0]["availability"] = multiply(group["schedule"][0]["availability"], a)
        if block_state["pump_available"] != 1 and not any(
            m.get("pump") for m in model["membranes"]
        ):
            raise ValueError("Independent carried blocker has no Na/K pump owner")
        for group in experiment.get("pump_controls", []):
            group["schedule"][0]["availability"] = multiply(
                group["schedule"][0]["availability"], block_state["pump_available"]
            )
    return changed


def integrate(
    raw,
    fields,
    binding_record,
    current_diffusion_m2_s,
    block_binding,
    block_state,
    *,
    start_time_s,
    end_time_s,
    events_enabled,
    refinement=1,
):
    points = grid(raw)
    if (
        type(refinement) is not int
        or refinement < 1
        or start_time_s not in points
        or end_time_s not in points
        or points.index(end_time_s) != points.index(start_time_s) + 1
    ):
        raise ValueError("Reference requires the next complete original grid interval")
    model = raw["model"].get("ionic", raw["model"])
    initial_blocks = dict(
        temperature_K=model["temperature_K"], boundary_voltage_V=[0.0] * 4, **block_state
    )
    after = setters.evaluate(
        block_binding["program"],
        initial_blocks,
        start_time_s,
        model["temperature_K"],
        events_enabled=events_enabled,
    )
    carried = {k: after[k] for k in block_state}
    changed = held_definition(
        raw,
        binding_record,
        current_diffusion_m2_s,
        block_binding,
        carried,
        control_time_s=start_time_s,
    )
    oracle = physical.ORACLES[raw["model"]["id"]]
    context = oracle.bind(changed)
    initial = oracle.flatten(context, fields)
    h = end_time_s - start_time_s
    atol = oracle.flatten(
        context,
        {
            k: np.full(s, (1e-29 if k.endswith("_C") else 2e-14) / refinement)
            for k, s in context["shapes"].items()
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
                    evaluations=evaluations,
                    original_start_s=start_time_s,
                    original_end_s=end_time_s,
                    held_definition=changed,
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
        max_step=h / (4 * refinement),
        first_step=h / (8 * refinement),
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
    right = held_definition(
        raw,
        binding_record,
        current_diffusion_m2_s,
        block_binding,
        carried,
        control_time_s=end_time_s,
    )
    endpoint = oracle.bind(right)
    rate, phi, proof = oracle.evaluate(endpoint, solved.y[:, -1], 0.0)
    return dict(
        context=context,
        state=solved.y[:, -1],
        endpoint_rate=rate,
        endpoint_potential_V=phi,
        endpoint_proof=proof,
        block_state=carried,
        setter_state=after,
        held_definition=changed,
        endpoint_definition=right,
        start_time_s=start_time_s,
        end_time_s=end_time_s,
        interval_s=h,
        evaluations=evaluations,
        refinement=refinement,
        rtol=2e-11 / refinement,
        state_atol=2e-14 / refinement,
        charge_atol_C=1e-29 / refinement,
        max_step_s=h / (4 * refinement),
        method="DOP853 on original interval; source blockers sampled once at its left label",
    )
