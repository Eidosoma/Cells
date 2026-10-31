"""Exact delegation to owned INIT/SIM and deterministic event producers."""

from collections.abc import Mapping

from cells.processes import betse_normal_ecm_molecule_events as events
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_lifecycle_phase as phase

source = lifecycle.catalog
MEMBRANE_KEYS = dict(Na_mem="Namem", K_mem="Kmem", Cl_mem="Clmem", Ca_mem="Camem")


def same_constant_authority(actual, expected):
    if isinstance(expected, Mapping):
        return (
            isinstance(actual, Mapping)
            and set(actual) == set(expected)
            and all(same_constant_authority(actual[key], value) for key, value in expected.items())
        )
    return type(actual) is type(expected) and actual == expected


def kind(binding):
    if type(binding) is phase.Binding:
        return binding.calendar.phase
    if type(binding) in (lifecycle.Binding, events.Binding):
        return "SIM"
    raise ValueError("Require the actual completed setup binding from frozen molecule54")


def verify_binding(binding):
    if type(binding) is phase.Binding:
        phase.verify_binding(binding)
        if binding.calendar.phase != "INIT":
            raise ValueError("SIM must retain its actual complete INIT transition association")
    elif type(binding) is lifecycle.Binding:
        lifecycle.validate_binding(binding)
    elif type(binding) is events.Binding:
        events.verify_binding(binding)
        event_scope(binding)
    else:
        raise ValueError("Foreign actual phase owner binding")


def event_scope(binding):
    """Existing global pulses and actual finalized constant membrane callbacks.

    The event module still checks complete source/phase/profile ownership.
    The callback declaration must equal the actual SIM finalizer return and
    its source/config/profile authority. No missing authority is regenerated.
    Event source equations and mutable stores are unchanged.
    """
    owner = binding.raw["event_owner"]
    if (
        set(owner["global_options"]) != set(events.event42.GLOBAL_KEYS)
        or set(owner["scheduled_options"]) != set(events.event42.TISSUE_KEYS)
        or any(owner["scheduled_options"][key] != 0 for key in ("pressure", "ecmJ"))
        or owner["voltage"] is not None
    ):
        raise ValueError(
            "Headless event checkpoint supports only deterministic global/constant membrane events"
        )
    selected = {
        key: suffix for key, suffix in MEMBRANE_KEYS.items() if owner["scheduled_options"][key] != 0
    }
    if set(owner["callbacks"]) != set(selected.values()):
        raise ValueError("Require exact actual finalized constant membrane callbacks")
    if not selected:
        return
    fields = binding.base.setup_receipt["event_finalization"].get("source_fields", {})
    if (
        "owner" not in fields
        or fields.get("source_phase") != "SIM"
        or fields.get("legacy_run_sim") is not True
        or fields.get("event_fire_calls") != 0
    ):
        raise ValueError("Missing actual finalized constant callback owner; no hydration allowed")
    original = fields["owner"]
    authority = fields.get("constant_callback_authority", {})
    published = lifecycle.event_owner_bridge.resolve(binding.source_binding, binding.source_entry)
    if not lifecycle.event_owner_bridge.same(published.event_finalized, fields):
        raise ValueError("Foreign actual finalized callback publication association")
    original = published.owner
    for key, suffix in selected.items():
        row, callback = owner["scheduled_options"][key], owner["callbacks"][suffix]
        if (
            len(row) != 6
            or row[5] != "None"
            or callback["source_function"] != "None"
            or callback["dynamic"] != {"kind": "constant"}
            or type(callback["source_scalar"]) is not int
            or callback["source_scalar"] != 1
            or not source.equal_tree(callback, original["callbacks"].get(suffix))
            or not source.equal_tree(row, original["scheduled_options"][key])
            or not same_constant_authority(
                authority.get(suffix), lifecycle.setup.constant_callback_record(suffix)
            )
        ):
            raise ValueError(
                "Require unchanged actual finalized constant callback/config authority: " + key
            )
        for stem in (
            "targets_",
            "apply_",
            "function_",
            "t_on_",
            "t_off_",
            "t_change_",
            "mem_mult_",
        ):
            name = stem + suffix
            if not source.equal_tree(
                owner["handler_fields"][name], original["handler_fields"][name]
            ):
                raise ValueError(
                    "Changed actual finalized membrane target/config ownership: " + name
                )


def calendar(binding):
    verify_binding(binding)
    if type(binding) is events.Binding:
        return binding.calendar
    return binding.calendar if type(binding) is phase.Binding else binding.declaration.calendar


def call_limit(binding):
    if type(binding) is events.Binding:
        return binding.call_limit
    return (
        binding.call_limit
        if type(binding) is phase.Binding
        else binding.declaration.inputs["stop_after_calls"]
    )


def profile(binding):
    if type(binding) is events.Binding:
        return binding.base.inputs_raw["time_profile"]
    return (
        binding.inputs_raw["time_profile"]
        if type(binding) is phase.Binding
        else binding.inputs["sim_phase"]["time_profile"]
    )


def phase_state(value):
    if type(value) in (phase.State, events.State):
        return value
    if type(value) is lifecycle.SimPhase:
        return value.active
    raise ValueError("Require a complete actual molecule54 phase state")


def cursor(value):
    return phase_state(value).cursor


def verify(binding, value):
    if type(binding) is phase.Binding:
        phase.verify(binding, value)
    elif type(binding) is events.Binding:
        event_scope(binding)
        events.verify(binding, value)
    else:
        lifecycle.verify(binding, value)


def phase_binding(binding, value):
    """Select the retained phase owner without reconstructing any state."""
    if type(binding) is events.Binding:
        if type(value) is not events.State or value.binding_identity != binding.identity:
            raise ValueError("Foreign event state/phase owner association")
        return binding.base
    if type(binding) is phase.Binding:
        return binding
    if type(binding) is lifecycle.Binding and type(value) is lifecycle.SimPhase:
        return value.phase_binding
    raise ValueError("Foreign typed phase owner binding/state")


def source_init(binding, value):
    if type(binding) is events.Binding:
        if type(value) is not events.State or value.binding_identity != binding.identity:
            raise ValueError("Foreign event state/source INIT association")
        return binding.source_entry.source_init
    if type(binding) is lifecycle.Binding and type(value) is lifecycle.SimPhase:
        return value.source_init
    raise ValueError("Foreign typed source INIT binding/state")


def advance(binding, value, *, phase_observer=None, **callbacks):
    verify(binding, value)
    if type(binding) is phase.Binding:
        return phase.advance(binding, value, observer=phase_observer, **callbacks)
    if type(binding) is events.Binding:
        return events.advance(binding, value, observer=phase_observer, **callbacks)
    return lifecycle.advance(binding, value, observer=phase_observer, **callbacks)


def sample(binding, value):
    verify(binding, value)
    if type(binding) is events.Binding:
        raise ValueError("Native storage/display remains unsupported for owned event runs")
    current = phase_state(value)
    actual = phase_binding(binding, value)
    return phase.request_native_sample(actual, current)
