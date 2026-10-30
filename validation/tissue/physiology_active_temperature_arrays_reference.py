"""Independent point certificates, raw failure semantics and full held rates.

No production/JAX imports. Numerical safety substitutions are labelled and do
not admit the raw proposal or define another physical temperature policy.
"""

import math

import numpy as np

from validation.tissue import physiology_active_temperature_reference as held

POLICY = held.POLICY


def complete_world_axes(record):
    """Independent cardinality check against original declared prepared-world IDs."""
    count = len(record["prepared_world_ids"])
    scalar_shapes = [
        record[key]
        for key in (
            "temperature_shape",
            "step_shape",
            "certificate_temperature_shape",
            "certificate_step_shape",
        )
    ]
    return (
        count > 0
        and len(set(record["prepared_world_ids"])) == count
        and all(shape == [count] for shape in scalar_shapes)
        and all(shape and shape[0] == count for shape in record["all_leaf_shapes"])
    )


REASONS = (
    "temperature_finite",
    "temperature_domain",
    "temperature_certified",
    "controls_domain",
    "step_domain",
    "step_certified",
    "stage_domain",
    "field_converged",
    "finite_complete_rates",
    "stage_energy",
    "dissipation",
    "passive_turnover",
    "fuel_turnover",
)


def proposal_input_validity(temperature, step, controls, certified_temperature_K, maximum_step_s):
    """Independent six predicates, also replayable from raw nonfinite NPZ buffers."""
    return [
        math.isfinite(temperature),
        200 <= temperature <= 400,
        temperature == certified_temperature_K,
        all(
            np.isfinite(value).all() and np.all((np.asarray(value) >= 0) & (np.asarray(value) <= 1))
            for value in controls.values()
        ),
        math.isfinite(step) and step > 0,
        step <= maximum_step_s,
    ]


def evaluate(raw, fields, binding_record, certified_temperature_K, maximum_step_s, proposal):
    temperature, step = proposal["temperature_K"], proposal["step_s"]
    controls = proposal["control"]
    flags = proposal_input_validity(
        temperature, step, controls, certified_temperature_K, maximum_step_s
    )
    target = temperature if all(flags[:3]) else certified_temperature_K
    effective_control = (
        controls
        if flags[3]
        else {name: np.zeros_like(value).tolist() for name, value in controls.items()}
    )
    context, rate, phi, proof = held.evaluate(
        raw, fields, binding_record, target, effective_control, 0.4, False
    )
    evidence = dict(
        proof,
        array_contract="cells.physiology_active_temperature_array_cohort@1",
        proposal_input_validity=flags,
        input_reason_mask=sum((0 if valid else 1 << i) for i, valid in enumerate(flags)),
        certified_temperature_K=certified_temperature_K,
        maximum_step_s=maximum_step_s,
        arithmetic_substitution=not all(flags),
        admitted_stepping=False,
    )
    return context, rate, phi, evidence
