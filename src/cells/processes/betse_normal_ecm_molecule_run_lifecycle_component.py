"""Exact delegation to frozen molecule54 INIT/SIM producers and validators."""

from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_lifecycle_phase as phase

source = lifecycle.catalog


def kind(binding):
    if type(binding) is phase.Binding:
        return binding.calendar.phase
    if type(binding) is lifecycle.Binding:
        return "SIM"
    raise ValueError("Require the actual completed setup binding from frozen molecule54")


def verify_binding(binding):
    if type(binding) is phase.Binding:
        phase.verify_binding(binding)
        if binding.calendar.phase != "INIT":
            raise ValueError("SIM must retain its actual complete INIT transition association")
    elif type(binding) is lifecycle.Binding:
        lifecycle.validate_binding(binding)
    else:
        raise ValueError("Foreign actual phase owner binding")


def calendar(binding):
    verify_binding(binding)
    return binding.calendar if type(binding) is phase.Binding else binding.declaration.calendar


def call_limit(binding):
    return (
        binding.call_limit
        if type(binding) is phase.Binding
        else binding.declaration.inputs["stop_after_calls"]
    )


def profile(binding):
    return (
        binding.inputs_raw["time_profile"]
        if type(binding) is phase.Binding
        else binding.inputs["sim_phase"]["time_profile"]
    )


def phase_state(value):
    if type(value) is phase.State:
        return value
    if type(value) is lifecycle.SimPhase:
        return value.active
    raise ValueError("Require a complete actual molecule54 phase state")


def cursor(value):
    return phase_state(value).cursor


def verify(binding, value):
    if type(binding) is phase.Binding:
        phase.verify(binding, value)
    else:
        lifecycle.verify(binding, value)


def advance(binding, value, *, phase_observer=None, **callbacks):
    verify(binding, value)
    if type(binding) is phase.Binding:
        return phase.advance(binding, value, observer=phase_observer, **callbacks)
    return lifecycle.advance(binding, value, observer=phase_observer, **callbacks)


def sample(binding, value):
    verify(binding, value)
    current = phase_state(value)
    actual = binding if type(binding) is phase.Binding else value.phase_binding
    return phase.request_native_sample(actual, current)
