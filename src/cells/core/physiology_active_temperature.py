"""Explicit fixed-empirical-kinetics isothermal contract over original active states.

This named opt-in binds physical owners and a native Kelvin setter. It neither
changes an ordinary model identity/domain nor admits a changed-T checkpoint.
"""

import math
from dataclasses import dataclass
from numbers import Real
from typing import NamedTuple

import numpy as np

from cells.core import physiology_temperature as original
from cells.core.specs import digest
from cells.processes import betse_global_controls as source

KIND = "cells.physiology_active_temperature_binding@1"
POLICY = "active_uniform_isothermal_fixed_empirical_kinetics@1"
REFERENCE_TEMPERATURE_K = 298.15
TEMPERATURE_DOMAIN_K = (200.0, 400.0)
MODEL_TYPES = original.MODEL_TYPES[1:]
TemperatureRejected = original.TemperatureRejected


@dataclass(frozen=True, slots=True)
class Binding:
    original_binding: original.Binding
    policy: str
    identity: str


class TemperatureMemory(NamedTuple):
    temperature_K: object


@dataclass(frozen=True, slots=True)
class Preparation:
    state: TemperatureMemory
    source_values: source.Values
    binding_identity: str
    event_time_s: float
    events_enabled: bool


def validate_source(spec):
    original._spec(spec)
    if type(spec.model) not in MODEL_TYPES:
        raise ValueError("Active isothermal views require one of the five exact active identities")
    return spec


def record(binding):
    if type(binding) is not Binding or binding.policy != POLICY:
        raise ValueError("Require the explicit versioned active-temperature policy binding")
    payload = dict(
        kind=KIND,
        policy=POLICY,
        original_binding=original.record(binding.original_binding),
        reference_temperature_K=REFERENCE_TEMPERATURE_K,
        temperature_domain_K=list(TEMPERATURE_DOMAIN_K),
        semantics="held_complete_active_rates_no_accepted_thermal_transition@1",
        standard_energy_policy="fixed_J_mol_ER_and_fuel_standard_coefficients@1",
        maintained_calcium_standard="declared_numeric_mM_standard_energy_J_mol_fixed@1",
        finite_calcium_standard="shared_1M_to_numeric_mM_deltaG0_minus_RT_ln1000@1",
        kinetics="fixed_empirical_curves_no_Q10_or_Arrhenius@1",
        native_compatibility="native_configured_runtime_split_is_separate_evidence@1",
    )
    return payload | dict(identity=digest(payload))


def bind(spec, program, *, owners, policy, provenance):
    validate_source(spec)
    if policy != POLICY:
        raise ValueError("Explicitly select the exact held active-temperature policy")
    inner = original.bind(spec, program, owners=owners, provenance=provenance)
    pending = Binding(inner, policy, "")
    return Binding(inner, policy, record(pending)["identity"])


def restore(saved, spec):
    validate_source(spec)
    if type(saved) is not dict or saved.get("kind") != KIND or saved.get("policy") != POLICY:
        raise ValueError("Require the complete named active-temperature contract")
    try:
        inner = original.restore(saved["original_binding"], spec)
        result = Binding(inner, POLICY, saved["identity"])
        if record(result) != saved:
            raise ValueError("Active-temperature policy/source/owner/standard-state mismatch")
        return result
    except (KeyError, TypeError) as error:
        raise ValueError("Malformed active-temperature binding") from error


def prepare(spec, binding, memory, *, time_s, events_enabled):
    validate_source(spec)
    if type(binding) is not Binding or binding.identity != record(binding)["identity"]:
        raise ValueError("Stale active-temperature binding")
    restore(record(binding), spec)
    if (
        not isinstance(time_s, Real)
        or isinstance(time_s, (bool, np.bool_))
        or not math.isfinite(time_s)
        or type(events_enabled) is not bool
    ):
        raise ValueError("Declare a finite source label and explicit native enable flag")
    if type(memory) is not TemperatureMemory:
        raise ValueError("Require the distinct held active-temperature memory type")
    current = np.asarray(memory.temperature_K)
    if current.shape != () or current.dtype != np.float64 or not np.isfinite(current):
        raise ValueError("Held active-temperature memory requires a float64 Kelvin scalar")
    if not TEMPERATURE_DOMAIN_K[0] <= current <= TEMPERATURE_DOMAIN_K[1]:
        raise ValueError("Held active-temperature memory leaves the 200-400 K process domain")
    program = binding.original_binding.program
    initial = source.State(
        current, np.ones(len(program.membrane_ids)), np.asarray(1.0), np.zeros(4)
    )
    with np.errstate(all="ignore"):
        values = source.apply(
            initial,
            source.compile_program(program),
            np.asarray(time_s, dtype=np.float64),
            np.asarray(REFERENCE_TEMPERATURE_K),
            events_enabled,
            xp=np,
        )
    target = values.state.temperature_K
    if (
        not values.physical_domain
        or not TEMPERATURE_DOMAIN_K[0] <= target <= TEMPERATURE_DOMAIN_K[1]
    ):
        raise TemperatureRejected(
            "Native setter leaves the declared held active-temperature process domain",
            dict(
                binding_identity=binding.identity,
                source_values=original.immutable._immutable_tree(values),
            ),
        )
    frozen = original.immutable._immutable_tree(values)
    return Preparation(
        TemperatureMemory(frozen.state.temperature_K),
        frozen,
        binding.identity,
        float(time_s),
        events_enabled,
    )
