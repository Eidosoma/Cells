"""Local charged RK4 trials against independently refined complete-state ODEs."""

import numpy as np
import pytest

from cells.core import physiology_protein_charge_step as step
from cells.core import physiology_tissue_binding as units
from cells.core import physiology_tissue_step as tissue
from tests.integration.test_physiology_protein_charge_rhs import evaluate
from tests.integration.test_physiology_protein_charge_view import active_nodes, changed_protein
from tests.unit.test_physiology_permeability_view import exact_tree, fingerprints
from tests.unit.test_physiology_tissue_step import KINDS, case, control, evidence
from validation.tissue import physiology_protein_charge_step_reference as reference


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("evolved", [False, True])
def test_complete_held_charge_interval_matches_refined_independent_ODE(kind, evolved):
    spec, point, binding, anchor, implementation = case(kind, source_dt_scale=0.5)
    if evolved:
        point = tissue.advance(spec, point, binding, anchor).checkpoint
    current = changed_protein(binding, anchor)
    admitted = evaluate(spec, point, binding, anchor, current)
    layout, delta = admitted.original.runtime_layout, admitted.rates.protein_charge_increment_C
    held, h = control(spec, point.time), spec.execution.dt / 4
    before = fingerprints(spec, point.state, point.layout, current)
    coarse = step.array_rk4_step(
        point.state, held, layout, delta, h, implementation=implementation, xp=np
    )
    half = step.array_rk4_step(
        point.state, held, layout, delta, h / 2, implementation=implementation, xp=np
    )
    fine = step.array_rk4_step(
        half.proposed_state, held, layout, delta, h / 2, implementation=implementation, xp=np
    )
    assert coarse.valid and half.valid and fine.valid
    parameters = dict(
        raw=spec.to_dict(),
        fields=point.state._asdict(),
        binding=units.binding_record(binding),
        current_diffusion=current.diffusion.current_m2_s,
        held_control=held._asdict(),
        before=anchor.protein._asdict(),
        after=current.protein._asdict(),
        valence=-1,
        duration_s=h,
    )
    standard = reference.integrate(**parameters)
    tight = reference.integrate(**parameters, refinement=2)
    context = tight["context"]
    oracle = reference.rates.permeability.ORACLES[spec.to_dict()["model"]["id"]]
    target = tight["state"]
    budget = oracle.flatten(
        context,
        {
            name: np.full(shape, 3e-23 if name.endswith("_C") else 3e-12)
            for name, shape in context["shapes"].items()
        },
    ) + 3e-10 * abs(target)
    actual = oracle.flatten(context, coarse.proposed_state._asdict())
    refined = oracle.flatten(context, fine.proposed_state._asdict())
    phi_budget = 3e-13 + 3e-10 * abs(tight["endpoint_potential_V"])
    phis = [
        active_nodes(
            point,
            step.charged.array_readouts(
                trial.proposed_state, held, layout, delta, implementation=implementation, xp=np
            ).field.potential_V,
        )
        for trial in (coarse, fine)
    ]
    errors = dict(
        state=float(np.max(abs(actual - target) / budget)),
        refined_state=float(np.max(abs(refined - target) / budget)),
        reference_state=float(np.max(abs(standard["state"] - target) / budget)),
        potential=float(np.max(abs(phis[0] - tight["endpoint_potential_V"]) / phi_budget)),
        refined_potential=float(np.max(abs(phis[1] - tight["endpoint_potential_V"]) / phi_budget)),
        reference_potential=float(
            np.max(
                abs(standard["endpoint_potential_V"] - tight["endpoint_potential_V"]) / phi_budget
            )
        ),
    )
    evidence(
        "protein-charge-interval-" + kind + "-" + str(evolved),
        dict(
            **parameters,
            numeric_start_time_s=point.time,
            comparisons=errors,
            complete_fields=len(point.state),
            local_operator_only=True,
            accepted_checkpoint=False,
            ordinary_history_fixture=True,
            reference_evaluations=[standard["evaluations"], tight["evaluations"]],
        ),
        dict(
            actual=actual,
            refined=refined,
            expected=target,
            standard=standard["state"],
            state_budget=budget,
            actual_phi=phis[0],
            refined_phi=phis[1],
            expected_phi=tight["endpoint_potential_V"],
            standard_phi=standard["endpoint_potential_V"],
            phi_budget=phi_budget,
        ),
    )
    assert all(value <= 1 for value in errors.values())
    assert errors["reference_state"] <= 0.1 and errors["reference_potential"] <= 0.1
    # Both timesteps independently meet the same budgets. No convergence order
    # is inferred from errors near the reference or floating-point uncertainty.
    assert all(
        abs(float(s.energy_rate_residual_pJ_s)) <= 1e-10
        for trial in (coarse, half, fine)
        for s in trial.status
    )
    assert fingerprints(spec, point.state, point.layout, current) == before


@pytest.mark.parametrize("kind", ["passive", "fuel"])
def test_zero_charge_trial_is_exact_original_RK4(kind):
    spec, point, binding, anchor, implementation = case(kind)
    admitted = evaluate(spec, point, binding, anchor, anchor)
    layout, held, h = (
        admitted.original.runtime_layout,
        control(spec, point.time),
        spec.execution.dt / 4,
    )
    original = tissue.array_rk4_step(
        point.state, held, layout, h, implementation=implementation, xp=np
    )
    result = step.array_rk4_step(
        point.state,
        held,
        layout,
        admitted.rates.protein_charge_increment_C,
        h,
        implementation=implementation,
        xp=np,
    )
    exact_tree(result, original)


def test_intermediate_refusal_is_retained_and_prevents_valid_trial(monkeypatch):
    spec, point, binding, anchor, implementation = case()
    admitted = evaluate(spec, point, binding, anchor, changed_protein(binding, anchor))
    original, calls = step.charged.array_readouts, []

    def inject(*args, **kwargs):
        value = original(*args, **kwargs)
        calls.append(value)
        return value._replace(valid=np.asarray(False)) if len(calls) == 2 else value

    monkeypatch.setattr(step.charged, "array_readouts", inject)
    before = fingerprints(spec, point.state, point.layout, anchor)
    result = step.array_rk4_step(
        point.state,
        control(spec, point.time),
        admitted.original.runtime_layout,
        admitted.rates.protein_charge_increment_C,
        spec.execution.dt / 4,
        implementation=implementation,
        xp=np,
    )
    assert not result.valid and result.first_invalid_stage == 1
    assert not result.status[1].field_valid and len(result.stages) == 5
    assert fingerprints(spec, point.state, point.layout, anchor) == before


@pytest.mark.parametrize("duration", [0.0, -1e-6])
def test_nonpositive_duration_never_produces_valid_trial(duration):
    spec, point, binding, anchor, implementation = case()
    admitted = evaluate(spec, point, binding, anchor, anchor)
    with np.errstate(invalid="ignore"):
        result = step.array_rk4_step(
            point.state,
            control(spec, point.time),
            admitted.original.runtime_layout,
            admitted.rates.protein_charge_increment_C,
            duration,
            implementation=implementation,
            xp=np,
        )
    assert not result.valid and result.first_invalid_stage == 0
